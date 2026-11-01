# Segurança e proteção de dados

O projeto trata dados de saúde como dados pessoais sensíveis. As mudanças técnicas seguem uma premissa brasileira, com referência à [LGPD](https://presidencia.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm) e às orientações da [ANPD sobre segurança da informação](https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/anonimizado___guia_orientat-_seg_da_inf_p_atpp.pdf).

## Controles implementados

- MySQL mantém os dados em tabelas InnoDB e expõe à aplicação apenas views agregadas protegidas com `SQL SECURITY DEFINER`.
- A aplicação usa uma conta MySQL restrita: leitura das views, leitura limitada de `app_users`, atualização de `password_hash` e operações necessárias em sessões e tentativas de login. Não usa `root` nem lê tabelas clínicas diretamente.
- A autenticação usa senha derivada com scrypt, sessão aleatória de 256 bits com apenas o hash SHA-256 persistido, cookie `HttpOnly`, `SameSite=Strict` e `Secure` em produção.
- O login limita tentativas por e-mail e IP; esses valores são armazenados como HMAC, com segredo dedicado.
- As views analíticas não retornam identificadores individuais e ocultam grupos com menos de 10 internações. Esse limiar reduz exposição, mas não garante anonimização contra cruzamentos ou ataques por diferença.
- A transformação SIH/SUS usa HMAC-SHA-256 com segredo local e remove número AIH, idade exata e município dos artefatos processados.
- A readmissão fica `NULL` nos dados reais quando a fonte não permite reconhecer a mesma pessoa. O benchmark mantém apenas valores simulados.
- A carga remota exige TLS validado e uma conta ETL dedicada. A substituição completa dos dados requer duas flags explícitas.
- Arquivos brutos e processados ficam fora do Git. Mantenha volumes locais criptografados e controle também os backups.
- A Vercel envia cabeçalhos de segurança; APIs respondem com `Cache-Control: no-store`.

Pseudonimização não é anonimização. Os arquivos processados de SIH/SUS continuam contendo informação clínica por internação e devem permanecer em ambiente controlado.

## Configuração necessária antes de produção

1. Execute `sql/mysql_setup.sql` como administrador do banco; crie depois as contas separadas descritas em `sql/mysql_grants.sql`.
2. Configure a Vercel com `MYSQL_URL` da conta `dashboard_app`, `MYSQL_TLS=true`, a CA validada em `MYSQL_SSL_CA` quando necessária, `MYSQL_CONNECTION_LIMIT=2` e `AUTH_RATE_LIMIT_SECRET` aleatório com pelo menos 32 caracteres.
3. Crie ou atualize a conta autorizada usando o script interativo local. O bootstrap não deve rodar na Vercel nem usar a URL da conta da aplicação.
4. Guarde e faça backup de `PATIENT_DATA_HMAC_KEY`; alterá-lo requer recarga planejada dos dados.
5. Para Power BI, use `powerbi_reader` com `SELECT` somente nas views agregadas.
6. Antes de substituir dados, faça backup. Execute `src/load_to_mysql.py --truncate --confirm-truncate` apenas com a role ETL e depois recarregue o conjunto inteiro.
7. A organização deve definir finalidade e base legal, retenção, canal para titulares, responsáveis e contratos com operadores. A aplicação não determina esses elementos organizacionais.

A [Resolução CD/ANPD nº 15/2024](https://www.gov.br/anpd/pt-br/canais_atendimento/agente-de-tratamento/comunicado-de-incidente-de-seguranca-cis) prevê comunicação de incidente à ANPD e aos titulares no prazo aplicável quando os critérios de risco ou dano relevante forem atendidos; a regra geral é três dias úteis, com prazo em dobro para agentes de pequeno porte que se enquadrem na regulamentação específica. O controlador deve confirmar o prazo aplicável e manter um processo operacional para cumpri-lo.

Este documento descreve controles do repositório e passos de implantação; não certifica conformidade jurídica nem substitui avaliação do controlador e do encarregado de proteção de dados.
