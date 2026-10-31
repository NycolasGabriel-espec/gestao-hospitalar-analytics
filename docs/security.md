# Segurança e proteção de dados

O projeto trata dados de saúde como dados pessoais sensíveis. As mudanças técnicas seguem uma premissa brasileira, com referência à [LGPD](https://presidencia.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm) e às orientações da [ANPD sobre segurança da informação](https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/anonimizado___guia_orientat-_seg_da_inf_p_atpp.pdf).

## Controles implementados

- As tabelas do projeto mantêm RLS e não são concedidas diretamente a `anon` ou `authenticated`.
- O setup revoga grants padrão para novas tabelas e sequências criadas por `postgres` em `public`; qualquer objeto futuro precisa de grants explícitos e revisão de RLS.
- As rotas exigem uma conta Supabase aprovada em `app_metadata.hospital_analytics_access = true`; a autorização não usa `user_metadata`.
- O acesso usa links mágicos de uso único enviados apenas a contas existentes (`create_user=false`); não há senha nem cadastro público. As sessões do navegador ficam em cookies `HttpOnly`, `SameSite=Strict` e `Secure` em produção. As ações de sessão exigem origem igual à aplicação.
- As views não retornam identificadores individuais e suprimem grupos com menos de 10 internações; esse limiar reduz exposição, mas não garante anonimização contra cruzamentos ou ataques por diferença.
- A transformação SIH/SUS usa HMAC-SHA-256 com segredo local, remove número AIH, idade exata e município dos artefatos processados.
- A taxa de readmissão fica `NULL` nos dados reais quando a fonte não permite reconhecer a mesma pessoa. O benchmark mantém apenas valores simulados.
- Arquivos brutos e processados ficam fora do Git. A carga exige `service_role` somente em processo local e a carga destrutiva requer duas flags explícitas.
- Os diretórios locais de dados são criados com permissão de proprietário apenas em sistemas POSIX; mantenha volumes criptografados e controle também os backups.
- A Vercel envia cabeçalhos de segurança; APIs respondem com `Cache-Control: no-store`.

Pseudonimização não é anonimização. Os arquivos processados de SIH/SUS continuam contendo informação clínica por internação e devem permanecer em ambiente controlado.

## Configuração necessária antes de produção

1. Desative cadastro público no Supabase Auth e limite os redirecionamentos ao domínio da aplicação.
2. Conceda `hospital_analytics_access` apenas por fluxo administrativo confiável. O login deste protótipo não implementa desafio MFA; não declare MFA obrigatório até que o fluxo de step-up e uma regra AAL2 estejam impostos nas views/API.
3. Mantenha `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL` e `PATIENT_DATA_HMAC_KEY` fora do navegador, do Git e dos logs. Proteja e faça backup do segredo HMAC; alterá-lo requer recarga planejada dos dados.
4. Para Power BI, use `powerbi_reader` com acesso somente às views, nunca a senha mestre `postgres`.
5. Antes de substituir uma base antiga, faça backup. O setup altera permissões e colunas, mas não recalcula identificadores nem apaga linhas antigas; limpe e recarregue os dados com HMAC antes de habilitar usuários. Se dados reais ou segredos já foram commitados, eles podem continuar no histórico Git e exigem tratamento próprio.
6. A organização deve definir finalidade e base legal, retenção, canal para titulares, responsáveis e contratos com operadores. A aplicação não determina esses elementos organizacionais.
7. Configure limites de tentativa e monitoramento do Supabase Auth, restrinja origens/redirects e revise periodicamente usuários aprovados e acessos à base.

A [Resolução CD/ANPD nº 15/2024](https://www.gov.br/anpd/pt-br/canais_atendimento/agente-de-tratamento/comunicado-de-incidente-de-seguranca-cis) prevê comunicação de incidente à ANPD e aos titulares no prazo aplicável quando os critérios de risco ou dano relevante forem atendidos; a regra geral é três dias úteis, com prazo em dobro para agentes de pequeno porte que se enquadrem na regulamentação específica. O registro deve ser mantido por pelo menos cinco anos, ressalvadas obrigações adicionais ou regras aplicáveis a entidades públicas. O controlador deve confirmar o prazo aplicável e manter um processo operacional para cumpri-lo.

Este documento descreve controles do repositório e passos de implantação; não certifica conformidade jurídica nem substitui avaliação do controlador e do encarregado de proteção de dados.
