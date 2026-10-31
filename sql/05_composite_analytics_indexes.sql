-- Match the common month + bed / month + procedure filters in the BI views.
CREATE INDEX IF NOT EXISTS idx_fato_data_leito
  ON public.fato_internacoes (id_data_admissao, id_leito);
CREATE INDEX IF NOT EXISTS idx_fato_data_procedimento
  ON public.fato_internacoes (id_data_admissao, id_procedimento);
