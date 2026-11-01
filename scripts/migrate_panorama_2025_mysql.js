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
  await connection.query(await readFile('sql/08_panorama_2025_mysql.sql', 'utf8'));
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
  const [executive] = await appConnection.query('SELECT COUNT(*) AS aggregate_rows FROM vw_painel_executivo_mensal WHERE ano = 2025');
  const [risk] = await appConnection.query('SELECT COUNT(*) AS groups_2025 FROM vw_detalhe_clinico_risco WHERE ano = 2025');
  console.log(JSON.stringify({ ready: true, migration: '08_panorama_2025_mysql.sql', executiveGroups2025: Number(executive[0].aggregate_rows), riskGroups2025: Number(risk[0].groups_2025), tlsVerified: true }));
} catch (error) {
  console.error(JSON.stringify({ ready: false, errorCode: error.code || error.name }));
  process.exitCode = 1;
} finally {
  await appConnection?.end().catch(() => {});
  await connection.end().catch(() => {});
}
