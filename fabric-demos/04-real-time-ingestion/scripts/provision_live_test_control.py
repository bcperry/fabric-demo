import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from uuid import UUID

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
GROUP = 'fabric-mda-demo'
SUBSCRIPTION = 'a679b60b-99ab-4a54-ac23-2523c39342de'
TENANT = 'a9077aab-55ce-4dac-8343-89d30aeaa786'
REGISTRY = 'mdalive4u6mawdzlpyh4'
IDENTITY = 'id-mda-live-test-control'
APP = 'ca-mda-live-test-control'
DISPLAY_NAME = 'Live Test Control API'
PGHOST = 'pg-mda-demo-4u6mawdzlpyh4.postgres.database.azure.com'
PGADMIN = 'admin@mngenvmcap005042.onmicrosoft.com'
BUILD_FILES = ('Dockerfile', 'requirements.txt', 'app.py', 'store.py')


def report(**values):
    print(json.dumps(values, sort_keys=True), flush=True)


def az(*arguments):
    result = subprocess.run(['az', *arguments, '--only-show-errors', '-o', 'json'],
                            capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'Azure CLI failed')
    return json.loads(result.stdout) if result.stdout.strip() else None


def database(dbname='mdaoperations'):
    result = subprocess.run(
        ['az', 'account', 'get-access-token', '--resource',
         'https://ossrdbms-aad.database.windows.net', '--query', 'accessToken', '-o', 'tsv'],
        capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if result.returncode or not result.stdout.strip():
        raise RuntimeError('PostgreSQL Entra token acquisition failed; no token printed')
    token = result.stdout.strip()
    try:
        return psycopg.connect(host=PGHOST, dbname=dbname, user=PGADMIN,
                              password=token, sslmode='require', connect_timeout=10,
                              autocommit=True, row_factory=dict_row)
    except psycopg.Error as error:
        try:
            with urllib.request.urlopen('https://api.ipify.org', timeout=10) as response:
                report(egressIp=response.read().decode(), firewallChanged=False)
        except OSError:
            report(egressIp='unavailable', firewallChanged=False)
        raise RuntimeError(str(error).replace(token, '[REDACTED]')) from None


def preflight():
    account = az('account', 'show', '--query', '{subscription:id,tenant:tenantId}')
    if account != {'subscription': SUBSCRIPTION, 'tenant': TENANT}:
        raise RuntimeError('Unexpected Azure subscription or tenant; no changes made')
    with database() as connection:
        report(database=connection.execute('SELECT current_database() AS database, current_user AS admin').fetchone())
    job = az('containerapp', 'job', 'show', '-g', GROUP, '-n', 'job-mda-live-test',
             '--query', '{id:id,containers:properties.template.containers[].{image:image,command:command}}')
    if len(job['containers']) != 1 or job['containers'][0].get('command'):
        raise RuntimeError('Existing job must have one container and its approved entrypoint')
    job_image = job['containers'][0]['image']
    if not re.fullmatch(REGISTRY + r'\.azurecr\.io/target-vehicle@sha256:[0-9a-f]{64}', job_image):
        raise RuntimeError('Existing job image is not pinned to the expected registry and repository')
    environment = az('containerapp', 'env', 'show', '-g', GROUP, '-n', 'cae-mda-live-test-eastus2',
                     '--query', '{id:id,location:location}')
    if environment['location'].replace(' ', '').lower() != 'eastus2':
        raise RuntimeError('Unexpected Container Apps environment location')
    report(preflight='passed', jobResourceId=job['id'], jobImage=job_image,
           environmentResourceId=environment['id'], roleMap={}, runtimeDatabaseConnection='UNVERIFIED')
    return job_image


def identity():
    return az('identity', 'show', '-g', GROUP, '-n', IDENTITY,
              '--query', '{id:id,clientId:clientId,principalId:principalId}')


def deploy(parameters, name):
    result = az('deployment', 'group', 'create', '-g', GROUP, '-n', name, '--mode', 'Incremental',
                '--template-file', str(ROOT / 'infrastructure/live-test-control.bicep'),
                '--parameters', *parameters, '--query', 'properties.outputs')
    outputs = {key: value['value'] for key, value in result.items()}
    report(deployment=name, **outputs)
    return outputs


def provision_database():
    managed = identity()
    with database('postgres') as connection:
        with connection.transaction():
            principals = connection.execute(
                'SELECT * FROM pgaadauth_list_principals(false) WHERE rolname = %s', (IDENTITY,)).fetchall()
            if not principals:
                if connection.execute('SELECT 1 FROM pg_roles WHERE rolname = %s', (IDENTITY,)).fetchone():
                    raise RuntimeError('Existing database role is not an Entra principal; refusing to adopt it')
                connection.execute('SELECT * FROM pgaadauth_create_principal_with_oid(%s, %s, %s, false, false)',
                                   (IDENTITY, managed['principalId'], 'service'))
                principals = connection.execute(
                    'SELECT * FROM pgaadauth_list_principals(false) WHERE rolname = %s', (IDENTITY,)).fetchall()
            if len(principals) != 1 or str(principals[0]['objectid']) != managed['principalId']:
                raise RuntimeError('Database principal object ID mismatch')
            principal = principals[0]
            if principal['isadmin'] or str(principal['tenantid']) != TENANT:
                raise RuntimeError('Database principal must be nonadmin and in the approved tenant')
            elevated = connection.execute('''
                SELECT rolname FROM pg_roles WHERE rolname = %s
                AND (rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls)
                UNION ALL
                SELECT parent.rolname FROM pg_auth_members membership
                JOIN pg_roles child ON child.oid = membership.member
                JOIN pg_roles parent ON parent.oid = membership.roleid
                WHERE child.rolname = %s
                ''', (IDENTITY, IDENTITY)).fetchall()
            if elevated:
                raise RuntimeError('Runtime role has elevated attributes or role memberships; refusing to proceed')
    report(databasePrincipal=IDENTITY, identityPrincipalId=managed['principalId'], admin=False)
    with database() as connection:
        connection.execute("SELECT set_config('live_test_control.runtime_role', %s, false)", (IDENTITY,))
        connection.execute((ROOT / 'control_service/schema.sql').read_text())
        grants = connection.execute('''
            SELECT has_schema_privilege(%s, 'live_test_control', 'USAGE') AS schema_usage,
                   has_table_privilege(%s, 'live_test_control.runs', 'SELECT,INSERT') AS read_insert,
                   has_column_privilege(%s, 'live_test_control.runs', 'state', 'UPDATE') AS update_state,
                   has_column_privilege(%s, 'live_test_control.runs', 'execution_id', 'UPDATE') AS update_execution,
                   has_table_privilege(%s, 'live_test_control.runs', 'DELETE,TRUNCATE,UPDATE') AS broad_write,
                   has_schema_privilege(%s, 'live_test_control', 'CREATE') AS schema_create
            ''', (IDENTITY,) * 6).fetchone()
        if not all(grants[key] for key in ('schema_usage', 'read_insert', 'update_state', 'update_execution')):
            raise RuntimeError('Required scoped database grants are missing')
        if grants['broad_write'] or grants['schema_create']:
            raise RuntimeError('Runtime principal has excessive schema/table privileges')
        report(databaseSchema='live_test_control', runtimeRole=IDENTITY,
               identityPrincipalId=managed['principalId'], grants=grants, schemaTransaction='committed')


def registration(create):
    applications = az('ad', 'app', 'list', '--filter', "displayName eq 'Live Test Control API'",
                      '--query', '[].{id:id,appId:appId,signInAudience:signInAudience,public:isFallbackPublicClient,passwords:length(passwordCredentials),keys:length(keyCredentials),web:web.redirectUris,spa:spa.redirectUris,publicRedirects:publicClient.redirectUris}')
    if len(applications) > 1:
        raise RuntimeError('Ambiguous exact display name Live Test Control API; refusing to select an application')
    if not applications:
        if not create:
            raise RuntimeError('API registration is missing; run the registration phase first')
        created = az('ad', 'app', 'create', '--display-name', DISPLAY_NAME,
                     '--sign-in-audience', 'AzureADMyOrg', '--query', '{id:id,appId:appId}')
        report(createdApiApplicationObjectId=created['id'], apiClientId=created['appId'])
        return registration(create)
    application = applications[0]
    if (application['signInAudience'] != 'AzureADMyOrg' or application['public']
            or application['passwords'] or application['keys'] or application['web']
            or application['spa'] or application['publicRedirects']):
        raise RuntimeError('Existing API application is not a secretless, single-tenant, API-only registration')
    client_id = str(UUID(application['appId']))
    if create:
        body = {'identifierUris': ['api://' + client_id], 'api': {'requestedAccessTokenVersion': 2},
                'isFallbackPublicClient': False}
        az('rest', '--method', 'PATCH', '--url', 'https://graph.microsoft.com/v1.0/applications/' + application['id'],
           '--body', json.dumps(body))
        principals = az('ad', 'sp', 'list', '--filter', "appId eq '" + client_id + "'", '--query', '[].id')
        if len(principals) > 1:
            raise RuntimeError('Ambiguous API service principal')
        principal_id = principals[0] if principals else az('ad', 'sp', 'create', '--id', client_id, '--query', 'id')
        report(apiApplicationObjectId=application['id'], apiClientId=client_id,
               apiServicePrincipalId=principal_id, identifierUri='api://' + client_id,
               tokenVersion=2, adminConsentGranted=False, publicClientCreated=False)
    return client_id


def build():
    digest = hashlib.sha256()
    for name in BUILD_FILES:
        digest.update(name.encode() + b'\0' + (ROOT / 'control_service' / name).read_bytes())
    image = 'live-test-control:' + digest.hexdigest()[:20]
    with tempfile.TemporaryDirectory(prefix='live-test-control-build-') as directory:
        for name in BUILD_FILES:
            shutil.copyfile(ROOT / 'control_service' / name, Path(directory) / name)
        result = az('acr', 'build', '--registry', REGISTRY, '--image', image,
                    '--no-logs', '--timeout', '1800', '--query', '{runId:runId,status:status}', directory)
    report(build=result)
    image_digest = az('acr', 'repository', 'show', '-n', REGISTRY, '--image', image, '--query', 'digest')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image_digest):
        raise RuntimeError('ACR did not return a valid image digest')
    reference = REGISTRY + '.azurecr.io/live-test-control@' + image_digest
    report(controlImage=reference)
    return reference


def verify():
    app = az('containerapp', 'show', '-g', GROUP, '-n', APP,
             '--query', '{id:id,state:properties.provisioningState,revision:properties.latestReadyRevisionName,fqdn:properties.configuration.ingress.fqdn,image:properties.template.containers[0].image,scale:properties.template.scale,env:properties.template.containers[0].env}')
    environment = {entry['name']: entry.get('value') for entry in app.pop('env')}
    if environment.get('CONTROL_ROLE_MAP_JSON') != '{}':
        raise RuntimeError('Deployed role map is not empty')
    endpoint = 'https://' + app.pop('fqdn')
    for path, headers, expected in (
            ('/health', {}, 200), ('/catalog', {}, 401),
            ('/catalog', {'Authorization': 'Bearer invalid-control-test-token'}, 401)):
        request = urllib.request.Request(endpoint + path, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                status = response.status
        except urllib.error.HTTPError as error:
            status = error.code
        report(path=path, malformedToken=bool(headers), status=status, expected=expected)
        if status != expected:
            raise RuntimeError('HTTP verification failed')
    report(endpoint=endpoint, app=app, roleMap={}, validTokenTest='NOT_READY',
           runtimeDatabaseConnection='UNVERIFIED', protectedRunsStarted=False)


def main():
    parser = argparse.ArgumentParser(description='Provision only the isolated synthetic live-test control service.')
    parser.add_argument('--phase', choices=('preflight', 'identity', 'database', 'registration', 'build', 'deploy', 'verify', 'all'), default='preflight')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--control-image')
    arguments = parser.parse_args()
    if arguments.phase not in {'preflight', 'verify'} and not arguments.apply:
        parser.error('Mutating phases require --apply')
    job_image = preflight()
    phases = ('identity', 'database', 'registration', 'build', 'deploy', 'verify') if arguments.phase == 'all' else (arguments.phase,)
    control_image = arguments.control_image
    for phase in phases:
        if phase == 'identity':
            deploy(['deployApp=false'], 'live-test-control-identity')
        elif phase == 'database':
            provision_database()
        elif phase == 'registration':
            registration(True)
        elif phase == 'build':
            control_image = build()
        elif phase == 'deploy':
            if not control_image or not re.fullmatch(REGISTRY + r'\.azurecr\.io/live-test-control@sha256:[0-9a-f]{64}', control_image):
                raise RuntimeError('Deploy requires --control-image pinned to the control-service repository digest')
            client_id = registration(False)
            deploy(['deployApp=true', 'appClientId=' + client_id, 'controlImage=' + control_image,
                    'jobImage=' + job_image, 'roleMapJson={}'], 'live-test-control-app')
        elif phase == 'verify':
            verify()


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, psycopg.Error, OSError) as error:
        report(blocker=str(error), partialState='Review preceding successful phase outputs; no automatic rollback or firewall changes')
        raise SystemExit(1) from None