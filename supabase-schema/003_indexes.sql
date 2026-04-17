-- ============================================================
-- J-ARVIS V2 — Schema Supabase — 003 Indexes
-- Performance sur les queries fréquentes
-- ============================================================

-- ── contacts ──
CREATE INDEX IF NOT EXISTS idx_contacts_type ON contacts(type);
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);
CREATE INDEX IF NOT EXISTS idx_contacts_telephone ON contacts(telephone);
CREATE INDEX IF NOT EXISTS idx_contacts_siret ON contacts(siret);
CREATE INDEX IF NOT EXISTS idx_contacts_created_at ON contacts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_contacts_archived ON contacts(archived) WHERE archived = false;
CREATE INDEX IF NOT EXISTS idx_contacts_nom_trgm ON contacts USING gin(nom gin_trgm_ops);

-- ── projets ──
CREATE INDEX IF NOT EXISTS idx_projets_contact_id ON projets(contact_id);
CREATE INDEX IF NOT EXISTS idx_projets_statut ON projets(statut);
CREATE INDEX IF NOT EXISTS idx_projets_marque ON projets(marque);
CREATE INDEX IF NOT EXISTS idx_projets_marque_statut ON projets(marque, statut);
CREATE INDEX IF NOT EXISTS idx_projets_reference ON projets(reference);
CREATE INDEX IF NOT EXISTS idx_projets_created_at ON projets(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_projets_date_pose ON projets(date_pose) WHERE date_pose IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_projets_archived ON projets(archived) WHERE archived = false;

-- ── documents ──
CREATE INDEX IF NOT EXISTS idx_documents_projet_id ON documents(projet_id);
CREATE INDEX IF NOT EXISTS idx_documents_contact_id ON documents(contact_id);
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(type);
CREATE INDEX IF NOT EXISTS idx_documents_marque ON documents(marque);
CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_traite ON documents(traite) WHERE traite = false;

-- ── taches ──
CREATE INDEX IF NOT EXISTS idx_taches_projet_id ON taches(projet_id);
CREATE INDEX IF NOT EXISTS idx_taches_contact_id ON taches(contact_id);
CREATE INDEX IF NOT EXISTS idx_taches_statut ON taches(statut);
CREATE INDEX IF NOT EXISTS idx_taches_assignee ON taches(assignee);
CREATE INDEX IF NOT EXISTS idx_taches_persona ON taches(persona);
CREATE INDEX IF NOT EXISTS idx_taches_priorite ON taches(priorite);
CREATE INDEX IF NOT EXISTS idx_taches_echeance ON taches(echeance) WHERE statut NOT IN ('done', 'cancelled');
CREATE INDEX IF NOT EXISTS idx_taches_created_at ON taches(created_at DESC);
-- Composite : tâches actives par assignee (query la plus fréquente)
CREATE INDEX IF NOT EXISTS idx_taches_assignee_statut ON taches(assignee, statut) WHERE statut IN ('todo', 'in_progress', 'waiting');

-- ── file_humaine ──
CREATE INDEX IF NOT EXISTS idx_file_humaine_decision ON file_humaine(decision);
CREATE INDEX IF NOT EXISTS idx_file_humaine_urgence ON file_humaine(urgence);
CREATE INDEX IF NOT EXISTS idx_file_humaine_created_at ON file_humaine(created_at DESC);
-- Composite : décisions en attente (query PWA écran Actions)
CREATE INDEX IF NOT EXISTS idx_file_humaine_pending ON file_humaine(urgence, created_at DESC) WHERE decision = 'pending';

-- ── audit_logs ──
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs(actor);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_status ON audit_logs(status) WHERE status != 'success';
