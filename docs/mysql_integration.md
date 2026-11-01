# MySQL externo e aplicação na Vercel

A aplicação e suas rotas API são publicadas na Vercel. O banco precisa ser um serviço MySQL tradicional 8+ acessível pelas funções Vercel. A Vercel conecta bancos externos por variáveis de ambiente e integrações do [Marketplace](https://vercel.com/docs/storage); este projeto não hospeda um servidor MySQL dentro de uma função serverless.

## 1. Preparar a instância

Disponibilize um banco MySQL 8+ com armazenamento persistente, backups e um endpoint TLS acessível pela Vercel. Guarde a conexão administrativa em um cofre e use-a somente para preparar o esquema e as contas. O código não depende de um provedor específico.

A URL deve seguir o formato `mysql://usuario:senha@host:porta/banco`. Codifique caracteres especiais da senha na URL. Não envie a conexão nem a senha pelo chat ou para o Git.

A implantação atual usa MySQL 8.4 no Aiven Free e funções Node.js na Vercel. O plano gratuito tem 1 GB de armazenamento e pode ser desligado por inatividade; consulte os [limites do Aiven Free](https://aiven.io/docs/products/mysql/concepts/mysql-free-tier).

## 2. Criar o esquema e as contas

Conecte-se como administrador, selecione o banco e execute [mysql_setup.sql](../sql/mysql_setup.sql). O script cria tabelas, índices e views agregadas e preserva linhas existentes.

Em [mysql_grants.sql](../sql/mysql_grants.sql), substitua `hospital_analytics` pelo nome do banco e troque as senhas de exemplo. Execute como administrador. As permissões separam:

- `dashboard_app`: views agregadas e operações necessárias para autenticação;
- `analytics_loader`: leitura e carga das tabelas factuais e dimensionais;
- `powerbi_reader`: leitura somente das views agregadas.

As views usam `SQL SECURITY DEFINER`. O usuário que executar o setup precisa continuar ativo e manter leitura nas tabelas de origem. A aplicação nunca recebe a credencial administrativa.

O comando `npm run mysql:setup` automatiza esquema e grants. Ele lê `.env.mysql-admin.json` local com `adminUrl` e `ca`, gera senhas aleatórias para as três contas e salva as URLs em `.env.mysql-runtime.json`. Esses arquivos são ignorados pelo Git e recebem permissão 600. Se `.env.mysql-account.json` existir com `email` e `passwordHash` scrypt, a conta do dashboard também é aplicada; caso contrário, use o bootstrap interativo da seção 4.

## 3. Configurar a conexão local

Copie `.env.example` para `.env`. Configure `MYSQL_URL`, `MYSQL_TLS=true` e a CA fornecida pelo serviço quando ela não estiver no conjunto de CAs confiáveis do sistema. O cliente Node recebe o conteúdo PEM em `MYSQL_SSL_CA`; o Python recebe o caminho do PEM em `MYSQL_SSL_CA_FILE`.

Os clientes validam a cadeia do certificado e o hostname do servidor. Para desenvolvimento em localhost, `MYSQL_TLS=false` é permitido. Conexões remotas e produção exigem TLS.

## 4. Habilitar a conta do dashboard

Use temporariamente a conexão administrativa no `.env` local e execute:

```bash
INITIAL_ADMIN_EMAIL=usuario@hospital.org npm run mysql:bootstrap-user
```

O script solicita a senha sem exibi-la, gera um hash scrypt e habilita a conta. Ele cria a conta se ela não existir ou atualiza a senha caso já exista. Ele não deve ser executado na Vercel.

## 5. Carregar os dados

Os arquivos em `data/processed/` ficam fora do Git. Gere o benchmark sintético ou execute a extração e transformação de uma fonte autorizada. Para carregar, use a conexão `analytics_loader` no `.env` local:

```bash
python3 src/load_to_mysql.py --dry-run
python3 src/load_to_mysql.py
```

Para dados reais, execute primeiro `src/extract_sih_sus.py` e `src/transform_star_schema.py`, mantendo o mesmo segredo `PATIENT_DATA_HMAC_KEY` nas recargas. O carregador usa upsert e respeita a ordem das chaves estrangeiras. Uma substituição completa exige backup e as duas opções:

```bash
python3 src/load_to_mysql.py --truncate --confirm-truncate
```

## 6. Configurar e publicar na Vercel

Configure as variáveis do projeto Vercel nos ambientes necessários:

- `MYSQL_URL`: conexão da conta limitada `dashboard_app`;
- `MYSQL_TLS=true`;
- `MYSQL_SSL_CA`: PEM da CA do serviço, quando necessária;
- `MYSQL_CONNECTION_LIMIT=2`;
- `AUTH_RATE_LIMIT_SECRET`: segredo aleatório com pelo menos 32 caracteres.

Mantenha a senha administrativa, a conta ETL e a senha do usuário do dashboard fora das variáveis de produção. Depois de preparar banco, conta autorizada e carga inicial, publique a versão MySQL. Confirme a saúde da API e o login antes de concluir a migração.

Sem a instância e as variáveis de conexão, a versão MySQL não consegue autenticar. As views ficam vazias até uma carga dos arquivos processados. A conta anterior precisa ser habilitada no novo banco com o mesmo e-mail autorizado.

## Power BI

Use a conta `powerbi_reader`, o endpoint MySQL e TLS validado. Consulte [o guia Power BI](../powerbi/como_conectar_powerbi.md). As views ocultam grupos com menos de 10 internações e não expõem identificadores de pessoa ou atendimento.
