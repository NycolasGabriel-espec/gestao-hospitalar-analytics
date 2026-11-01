import { readFile } from 'node:fs/promises';
import { createConnection } from 'mysql2/promise';

const admin = JSON.parse(await readFile('.env.mysql-admin.json', 'utf8'));
const adminUrl = new URL(admin.adminUrl);
if (adminUrl.protocol !== 'mysql:' || !adminUrl.hostname || !adminUrl.password || !admin.ca?.includes('BEGIN CERTIFICATE')) {
  throw new Error('A configuração administrativa MySQL está incompleta.');
}

const ssl = { ca: admin.ca, rejectUnauthorized: true, verifyIdentity: true };
const connection = await createConnection({
  host: adminUrl.hostname,
  port: Number(adminUrl.port || 3306),
  user: decodeURIComponent(adminUrl.username),
  password: decodeURIComponent(adminUrl.password),
  ssl,
  connectTimeout: 15000,
  multipleStatements: true,
});
let appConnection;

try {
  await connection.query('USE `hospital_analytics`');
  await connection.query(await readFile('sql/07_public_sus_mysql.sql', 'utf8'));
  const grants = (await readFile('sql/mysql_grants.sql', 'utf8')).replace(/^CREATE USER.*;$/gm, '');
  await connection.query(grants);

  const runtime = JSON.parse(await readFile('.env.mysql-runtime.json', 'utf8'));
  const appUrl = new URL(runtime.urls.dashboard_app);
  appConnection = await createConnection({
    host: appUrl.hostname,
    port: Number(appUrl.port || 3306),
    user: decodeURIComponent(appUrl.username),
    password: decodeURIComponent(appUrl.password),
    database: 'hospital_analytics',
    ssl,
    connectTimeout: 15000,
  });
  const views = [
    'vw_public_sus_sih_mensal',
    'vw_public_sus_sih_procedimento_mensal',
    'vw_public_sus_sih_procedimento_anual',
    'vw_public_cnes_leitos_mensal',
    'vw_public_sih_ocupacao_estimada_mensal',
    'vw_public_sisreg_fila_procedimento',
    'vw_public_sus_dataset_manifest',
  ];
  for (const view of views) await appConnection.query(`SELECT COUNT(*) FROM \`${view}\``);
  console.log(JSON.stringify({ ready: true, migration: '07_public_sus_mysql.sql', webViewsReadable: views.length, tlsVerified: true }));
} catch (error) {
  console.error(JSON.stringify({ ready: false, errorCode: error.code || error.name }));
  process.exitCode = 1;
} finally {
  await appConnection?.end().catch(() => {});
  await connection.end().catch(() => {});
}
