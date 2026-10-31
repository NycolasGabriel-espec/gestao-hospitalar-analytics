-- Require a Supabase Auth user for all analytics tables and views.
-- API handlers also verify the access token and forward it to PostgREST.
alter table public.dim_tempo enable row level security;
alter table public.dim_paciente enable row level security;
alter table public.dim_procedimento enable row level security;
alter table public.dim_diagnostico enable row level security;
alter table public.dim_setor_leito enable row level security;
alter table public.fato_internacoes enable row level security;

drop policy if exists "Permitir leitura dim_tempo" on public.dim_tempo;
drop policy if exists "Permitir leitura dim_paciente" on public.dim_paciente;
drop policy if exists "Permitir leitura dim_procedimento" on public.dim_procedimento;
drop policy if exists "Permitir leitura dim_diagnostico" on public.dim_diagnostico;
drop policy if exists "Permitir leitura dim_setor_leito" on public.dim_setor_leito;
drop policy if exists "Permitir leitura fato_internacoes" on public.fato_internacoes;

create policy "Permitir leitura dim_tempo" on public.dim_tempo
  for select to authenticated using (true);
create policy "Permitir leitura dim_paciente" on public.dim_paciente
  for select to authenticated using (true);
create policy "Permitir leitura dim_procedimento" on public.dim_procedimento
  for select to authenticated using (true);
create policy "Permitir leitura dim_diagnostico" on public.dim_diagnostico
  for select to authenticated using (true);
create policy "Permitir leitura dim_setor_leito" on public.dim_setor_leito
  for select to authenticated using (true);
create policy "Permitir leitura fato_internacoes" on public.fato_internacoes
  for select to authenticated using (true);

revoke all on schema public from anon;
revoke all on all tables in schema public from anon, authenticated;
grant usage on schema public to authenticated;
grant select on all tables in schema public to authenticated;
