import { readFile, writeFile, chmod } from 'node:fs/promises';
import { randomBytes, randomUUID } from 'node:crypto';
import { createConnection } from 'mysql2/promise';

const databaseName = 'hospital_analytics';
const adminFile = '.env.mysql-admin.json';
const runtimeFile = '.env.mysql-runtime.json';
const accountFile = '.env.mysql-account.json';
const usernames = ['dashboard_app', 'analytics_loader', 'powerbi_reader'];
const admin = JSON.parse(await readFile(adminFile, 'utf8'));
const adminUrl = new URL(admin.adminUrl);
if (adminUrl.protocol !== 'mysql:' || !adminUrl.password || !admin.ca?.includes('BEGIN CERTIFICATE')) {
  throw new Error('A configuração administrativa MySQL está incompleta.');
}
const ssl = { ca: admin.ca, rejectUnauthorized: true, verifyIdentity: true };
const options = {
  host: adminUrl.hostname,
  port: Number(adminUrl.port || 3306),
  user: decodeURIComponent(adminUrl.username),
  password: decodeURIComponent(adminUrl.password),
  ssl,
  connectTimeout: 15000,
};

let runtime;
try { runtime = JSON.parse(await readFile(runtimeFile, 'utf8')); } catch (error) {
  if (error.code !== 'ENOENT') throw error;
  const passwords = Object.fromEntries(usernames.map((name) => [name, randomBytes(32).toString('base64url')]));
  const urls = Object.fromEntries(usernames.map((name) => {
    const url = new URL(adminUrl);
    url.username = name;
    url.password = passwords[name];
    url.pathname = `/${databaseName}`;
    url.search = '';
    url.hash = '';
    return [name, url.toString()];
  }));
  runtime = { urls, ca: admin.ca, authRateLimitSecret: randomBytes(32).toString('hex') };
  await writeFile(runtimeFile, JSON.stringify(runtime), { mode: 0o600 });
}
await chmod(runtimeFile, 0o600);

let db;
let appDb;
try {
  db = await createConnection({ ...options, multipleStatements: true });
  await db.query(`CREATE DATABASE IF NOT EXISTS \`${databaseName}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci`);
  await db.query(`USE \`${databaseName}\``);
  await db.query(await readFile('sql/mysql_setup.sql', 'utf8'));
  await db.query(await readFile('sql/06_benchmark_mysql.sql', 'utf8'));
  await db.query(await readFile('sql/07_public_sus_mysql.sql', 'utf8'));
  for (const username of usernames) {
    const url = new URL(runtime.urls[username]);
    await db.query(`CREATE USER IF NOT EXISTS '${username}'@'%' IDENTIFIED BY ? REQUIRE SSL`, [decodeURIComponent(url.password)]);
  }
  const grants = (await readFile('sql/mysql_grants.sql', 'utf8'))
    .replace(/^CREATE USER.*;$/gm, '');
  await db.query(grants);

  let account;
  try { account = JSON.parse(await readFile(accountFile, 'utf8')); } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  if (account) {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(account.email) || !account.passwordHash?.startsWith('scrypt$')) {
      throw new Error('A configuração da conta do dashboard está incompleta.');
    }
    await db.beginTransaction();
    await db.execute(
      `INSERT INTO app_users (id, email, password_hash, hospital_analytics_access)
       VALUES (?, ?, ?, 1) ON DUPLICATE KEY UPDATE password_hash = VALUES(password_hash), hospital_analytics_access = 1`,
      [randomUUID(), account.email.toLowerCase(), account.passwordHash],
    );
    await db.execute('DELETE FROM auth_sessions WHERE user_id IN (SELECT id FROM app_users WHERE email = ?)', [account.email.toLowerCase()]);
    await db.commit();
  }

  const appUrl = new URL(runtime.urls.dashboard_app);
  appDb = await createConnection({ ...options, user: appUrl.username, password: appUrl.password, database: databaseName });
  await appDb.query('SELECT COUNT(*) FROM vw_painel_executivo_mensal');
  let baseTablesBlocked = false;
  try { await appDb.query('SELECT COUNT(*) FROM fato_internacoes'); } catch (error) {
    if (error.code === 'ER_TABLEACCESS_DENIED_ERROR') baseTablesBlocked = true;
    else throw error;
  }
  if (!baseTablesBlocked) throw new Error('A conta web não deveria ler tabelas clínicas.');
  const [objects] = await db.execute('SELECT TABLE_TYPE AS type, COUNT(*) AS total FROM information_schema.tables WHERE table_schema = ? GROUP BY TABLE_TYPE', [databaseName]);
  console.log(JSON.stringify({ ready: true, objects, authorizedAccount: account?.email || null, webBaseTablesBlocked: baseTablesBlocked, tlsVerified: true }));
} catch (error) {
  await db?.rollback().catch(() => {});
  console.error(JSON.stringify({ ready: false, errorCode: error.code || error.name }));
  process.exitCode = 1;
} finally {
  await appDb?.end().catch(() => {});
  await db?.end().catch(() => {});
}
