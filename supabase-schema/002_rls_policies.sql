-- ============================================================
-- J-ARVIS V2 — Schema Supabase — 002 RLS Policies
-- Row-Level Security activée sur toutes les tables
-- ============================================================
--
-- Stratégie RLS pour tenant isolé :
-- - Chaque tenant a son propre projet Supabase (pas de tenant_id dans les tables)
-- - RLS protège contre les accès non-authentifiés via anon key
-- - Le service_role key bypass RLS (utilisé par l'agent Jarvis côté serveur)
-- - Les policies ci-dessous permettent :
--   * SELECT/INSERT/UPDATE pour les users authentifiés (PWA)
--   * DELETE restreint (soft delete via archived=true)
--   * Audit logs en insert-only (pas de modification)

-- ============================================================
-- Activer RLS sur toutes les tables
-- ============================================================
ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE projets ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE taches ENABLE ROW LEVEL SECURITY;
ALTER TABLE file_humaine ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- Policy : contacts
-- ============================================================
CREATE POLICY "contacts_select" ON contacts FOR SELECT
    TO authenticated USING (true);

CREATE POLICY "contacts_insert" ON contacts FOR INSERT
    TO authenticated WITH CHECK (true);

CREATE POLICY "contacts_update" ON contacts FOR UPDATE
    TO authenticated USING (true) WITH CHECK (true);

-- Pas de DELETE — on utilise archived=true

-- ============================================================
-- Policy : projets
-- ============================================================
CREATE POLICY "projets_select" ON projets FOR SELECT
    TO authenticated USING (true);

CREATE POLICY "projets_insert" ON projets FOR INSERT
    TO authenticated WITH CHECK (true);

CREATE POLICY "projets_update" ON projets FOR UPDATE
    TO authenticated USING (true) WITH CHECK (true);

-- ============================================================
-- Policy : documents
-- ============================================================
CREATE POLICY "documents_select" ON documents FOR SELECT
    TO authenticated USING (true);

CREATE POLICY "documents_insert" ON documents FOR INSERT
    TO authenticated WITH CHECK (true);

CREATE POLICY "documents_update" ON documents FOR UPDATE
    TO authenticated USING (true) WITH CHECK (true);

-- ============================================================
-- Policy : taches
-- ============================================================
CREATE POLICY "taches_select" ON taches FOR SELECT
    TO authenticated USING (true);

CREATE POLICY "taches_insert" ON taches FOR INSERT
    TO authenticated WITH CHECK (true);

CREATE POLICY "taches_update" ON taches FOR UPDATE
    TO authenticated USING (true) WITH CHECK (true);

-- ============================================================
-- Policy : file_humaine
-- ============================================================
CREATE POLICY "file_humaine_select" ON file_humaine FOR SELECT
    TO authenticated USING (true);

CREATE POLICY "file_humaine_insert" ON file_humaine FOR INSERT
    TO authenticated WITH CHECK (true);

CREATE POLICY "file_humaine_update" ON file_humaine FOR UPDATE
    TO authenticated USING (true) WITH CHECK (true);

-- ============================================================
-- Policy : audit_logs (INSERT ONLY — jamais modifier/supprimer)
-- ============================================================
CREATE POLICY "audit_logs_select" ON audit_logs FOR SELECT
    TO authenticated USING (true);

CREATE POLICY "audit_logs_insert" ON audit_logs FOR INSERT
    TO authenticated WITH CHECK (true);

-- Pas de UPDATE ni DELETE sur audit_logs — immuable

-- ============================================================
-- Accès anon (PWA publique) — lecture seule limitée si besoin
-- Par défaut tout bloqué pour anon, on ouvre au cas par cas
-- ============================================================
-- Exemple : si la PWA publique doit lire des données
-- CREATE POLICY "public_read_projets" ON projets FOR SELECT
--     TO anon USING (statut IN ('livre', 'cloture'));
