import { readFile } from 'node:fs/promises';
import { createConnection } from 'mysql2/promise';

const admin = JSON.parse(await readFile('.env.mysql-admin.json', 'utf8'));
const adminUrl = new URL(admin.adminUrl);
if (adminUrl.protocol !== 'mysql:' || !adminUrl.hostname || !adminUrl.password || !admin.ca?.includes('BEGIN CERTIFICATE')) {
  throw new Error('A configuração administrativa MySQL está incompleta.');
}

const connection = await createConnection({
  host: adminUrl.hostname,
  port: Number(adminUrl.port || 3306),
  user: decodeURIComponent(adminUrl.username),
  password: decodeURIComponent(adminUrl.password),
  ssl: { ca: admin.ca, rejectUnauthorized: true, verifyIdentity: true },
  connectTimeout: 15000,
  multipleStatements: true,
});

try {
  await connection.query('USE `hospital_analytics`');
  await connection.query(await readFile('sql/06_benchmark_mysql.sql', 'utf8'));
  const grants = (await readFile('sql/mysql_grants.sql', 'utf8')).replace(/^CREATE USER.*;$/gm, '');
  await connection.query(grants);
  await connection.query('SELECT COUNT(*) FROM vw_benchmark_metadata');
  console.log(JSON.stringify({ ready: true, migration: '06_benchmark_mysql.sql', grantsUpdated: true, tlsVerified: true }));
} catch (error) {
  console.error(JSON.stringify({ ready: false, errorCode: error.code || error.name }));
  process.exitCode = 1;
} finally {
  await connection.end().catch(() => {});
}
