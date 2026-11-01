import { randomUUID } from 'node:crypto';
import { createPool } from 'mysql2/promise';
import { hashPassword } from '../lib/api/mysql.js';

function readHidden(prompt) {
  if (!process.stdin.isTTY || typeof process.stdin.setRawMode !== 'function') {
    throw new Error('Execute este comando em um terminal interativo para digitar a senha com segurança.');
  }
  process.stdout.write(prompt);
  process.stdin.setRawMode(true);
  process.stdin.resume();
  return new Promise((resolve, reject) => {
    let value = '';
    const onData = (buffer) => {
      for (const character of buffer.toString('utf8')) {
        if (character === '\u0003') {
          process.stdin.off('data', onData);
          process.stdin.setRawMode(false);
          process.stdin.pause();
          process.stdout.write('\n');
          reject(new Error('Operação cancelada.'));
          return;
        }
        if (character === '\r' || character === '\n') {
          process.stdin.off('data', onData);
          process.stdin.setRawMode(false);
          process.stdin.pause();
          process.stdout.write('\n');
          resolve(value);
          return;
        }
        if (character === '\u007f' || character === '\b') {
          value = value.slice(0, -1);
        } else if (character >= ' ') {
          value += character;
        }
      }
    };
    process.stdin.on('data', onData);
  });
}

const email = String(process.env.INITIAL_ADMIN_EMAIL || '').trim().toLowerCase();
if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 254) {
  throw new Error('Defina INITIAL_ADMIN_EMAIL com o e-mail autorizado para o dashboard.');
}

const password = await readHidden('Nova senha da conta: ');
const confirmation = await readHidden('Confirme a senha: ');
if (password !== confirmation) throw new Error('As senhas não coincidem.');
const passwordHash = await hashPassword(password);

const configuredUrl = process.env.MYSQL_URL;
let parsed;
try { parsed = new URL(configuredUrl); } catch { parsed = null; }
if (!parsed || parsed.protocol !== 'mysql:' || !parsed.hostname || !parsed.username || !parsed.password || parsed.pathname.length < 2) {
  throw new Error('Configure MYSQL_URL com a conexão de administração do MySQL.');
}
const tlsEnabled = process.env.MYSQL_TLS === 'true';
const localHost = ['localhost', '127.0.0.1', '::1'].includes(parsed.hostname);
if (!tlsEnabled && !localHost) throw new Error('Conexões remotas precisam usar TLS.');

const pool = createPool({
  host: parsed.hostname,
  port: Number(parsed.port || 3306),
  user: decodeURIComponent(parsed.username),
  password: decodeURIComponent(parsed.password),
  database: decodeURIComponent(parsed.pathname.slice(1)),
  ssl: tlsEnabled ? {
    rejectUnauthorized: true,
    verifyIdentity: true,
    ...(process.env.MYSQL_SSL_CA ? { ca: process.env.MYSQL_SSL_CA } : {}),
  } : undefined,
  connectionLimit: 1,
  connectTimeout: 10000,
});

try {
  await pool.execute(
    `INSERT INTO app_users (id, email, password_hash, hospital_analytics_access)
     VALUES (?, ?, ?, 1)
     ON DUPLICATE KEY UPDATE password_hash = VALUES(password_hash), hospital_analytics_access = 1`,
    [randomUUID(), email, passwordHash],
  );
  console.log(`Acesso ao dashboard configurado para ${email}.`);
} catch {
  console.error('Não foi possível configurar a conta. Confira a conexão MySQL, TLS, esquema e permissões.');
  process.exitCode = 1;
} finally {
  await pool.end();
}
