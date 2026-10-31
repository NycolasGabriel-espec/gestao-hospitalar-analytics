-- Remove standalone indexes that do not support the repository's query patterns.
-- Keep all indexes on foreign-key columns and all primary-key indexes.
DROP INDEX IF EXISTS public.idx_fato_readmissao;
DROP INDEX IF EXISTS public.idx_fato_margem;
DROP INDEX IF EXISTS public.idx_fato_obito;
