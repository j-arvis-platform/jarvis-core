-- ============================================================
-- J-ARVIS V2 — Schema Supabase — 001 Init Tables
-- 5 tables core + extensions
-- Isolation par tenant (1 projet Supabase = 1 tenant)
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- recherche floue

-- ============================================================
-- TABLE 1 : contacts
-- Clients, prospects, fournisseurs, partenaires
-- ============================================================
CREATE TABLE IF NOT EXISTS contacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type TEXT NOT NULL CHECK (type IN ('client', 'prospect', 'fournisseur', 'partenaire', 'sous_traitant')),

    -- Identité
    nom TEXT NOT NULL,
    prenom TEXT,
    raison_sociale TEXT,
    siret TEXT,

    -- Coordonnées
    email TEXT,
    telephone TEXT,
    telephone_2 TEXT,

    -- Adresse
    adresse JSONB DEFAULT '{}'::jsonb,
    -- Format : {"rue": "", "cp": "", "ville": "", "departement": "", "pays": "France", "lat": null, "lng": null}

    -- Commercial
    source TEXT,  -- site_web, bouche_a_oreille, google, facebook, parrainage, salon, demarchage
    score_prospect INTEGER DEFAULT 0 CHECK (score_prospect BETWEEN 0 AND 100),

    -- Metadata flexible
    metadata JSONB DEFAULT '{}'::jsonb,
    tags TEXT[] DEFAULT '{}',

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by TEXT DEFAULT 'jarvis',
    archived BOOLEAN DEFAULT FALSE
);

-- ============================================================
-- TABLE 2 : projets
-- Chantiers, missions, dossiers (multi-marques)
-- ============================================================
CREATE TABLE IF NOT EXISTS projets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contact_id UUID NOT NULL REFERENCES contacts(id) ON DELETE RESTRICT,

    -- Identification
    reference TEXT UNIQUE,  -- ELX-2026-0001, format auto
    titre TEXT NOT NULL,

    -- Typage multi-marques
    marque TEXT NOT NULL DEFAULT 'solarstis' CHECK (marque IN (
        'solarstis',              -- Photovoltaïque (marque commerciale ELEXITY)
        'domotique',              -- Jarvis Maison / domotique
        'bornes_ve',              -- Bornes de recharge VE
        'climatisation',          -- Clim / PAC
        'electricite_generale',   -- Elec générale
        'admin'                   -- Actions transversales (compta, RH, etc.)
    )),
    type TEXT NOT NULL,  -- chantier_pv, install_domotique, audit_energetique, maintenance, sav, devis_seul...

    -- Pipeline
    statut TEXT NOT NULL DEFAULT 'prospect' CHECK (statut IN (
        'prospect', 'qualification', 'vt_planifiee', 'vt_realisee',
        'devis_envoye', 'devis_relance', 'signe', 'en_attente_admin',
        'en_cours', 'pose_terminee', 'consuel', 'mise_en_service',
        'livre', 'sav', 'cloture', 'perdu', 'annule'
    )),

    -- Dates clés
    date_debut DATE,
    date_fin DATE,
    date_signature DATE,
    date_pose DATE,
    date_consuel DATE,
    date_mise_en_service DATE,

    -- Financier
    montant_ht NUMERIC(12,2),
    montant_ttc NUMERIC(12,2),
    taux_tva NUMERIC(4,2) DEFAULT 20.00,  -- 5.50 ou 20.00
    marge_ht NUMERIC(12,2),

    -- Technique PV (dans metadata si autre marque)
    puissance_kwc NUMERIC(6,2),
    nb_panneaux INTEGER,

    -- Metadata flexible (specs techniques, notes, etc.)
    metadata JSONB DEFAULT '{}'::jsonb,
    tags TEXT[] DEFAULT '{}',

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by TEXT DEFAULT 'jarvis',
    archived BOOLEAN DEFAULT FALSE
);

-- ============================================================
-- TABLE 3 : documents
-- Factures, devis, contrats, photos, PV, attestations
-- ============================================================
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    projet_id UUID REFERENCES projets(id) ON DELETE SET NULL,
    contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,

    -- Classification
    type TEXT NOT NULL CHECK (type IN (
        -- Commerciaux
        'devis_vente', 'devis_achat', 'contrat_client', 'contrat_fournisseur',
        -- Financiers
        'facture_vente', 'facture_achat', 'avoir', 'bon_commande',
        -- Techniques PV
        'consuel', 'dp_mairie', 'crae_edf', 'enedis_raccordement', 'pv_reception',
        'attestation_conformite',
        -- Administratifs
        'attestation_rge', 'attestation_decennale', 'urssaf', 'tva',
        'kbis', 'rib', 'mandat',
        -- Médias
        'photo_chantier', 'photo_vt', 'plan_3d', 'plan_calepinage',
        -- Autre
        'courrier', 'email', 'autre'
    )),
    marque TEXT NOT NULL DEFAULT 'solarstis' CHECK (marque IN (
        'solarstis', 'domotique', 'bornes_ve', 'climatisation',
        'electricite_generale', 'admin'
    )),

    -- Fichier
    nom_fichier TEXT NOT NULL,
    url_storage TEXT,  -- Supabase Storage path
    mime_type TEXT,
    taille_octets BIGINT,

    -- Données extraites (OCR, IA)
    metadata JSONB DEFAULT '{}'::jsonb,
    -- Format typique : {"montant_ht": 1234.56, "date_document": "2026-04-17", "numero": "F-2026-042", "ocr_text": "..."}

    -- Source et traitement
    source TEXT DEFAULT 'manual' CHECK (source IN ('jarvis', 'koncile', 'manual', 'email', 'whatsapp', 'scan')),
    traite BOOLEAN DEFAULT FALSE,  -- true quand Jarvis a fini de traiter

    -- Stockage tiéré
    tier_storage TEXT DEFAULT 'hot' CHECK (tier_storage IN ('hot', 'warm', 'cold')),
    -- hot = Supabase (3 mois), warm = Nextcloud (10 ans), cold = OVH Archive (30 ans)

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by TEXT DEFAULT 'jarvis'
);

-- ============================================================
-- TABLE 4 : taches
-- À faire par Jarvis ou humain
-- ============================================================
CREATE TABLE IF NOT EXISTS taches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    projet_id UUID REFERENCES projets(id) ON DELETE SET NULL,
    contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,

    -- Contenu
    titre TEXT NOT NULL,
    description TEXT,

    -- Attribution
    assignee TEXT NOT NULL DEFAULT 'jarvis',  -- jarvis, hamid, employe_xxx
    persona TEXT,  -- lea, claire, hugo, sofia, adam, yasmine, noah, elias

    -- Statut
    statut TEXT NOT NULL DEFAULT 'todo' CHECK (statut IN ('todo', 'in_progress', 'waiting', 'done', 'blocked', 'cancelled')),
    priorite TEXT NOT NULL DEFAULT 'normale' CHECK (priorite IN ('critique', 'urgent', 'normale', 'basse')),

    -- Timing
    echeance TIMESTAMPTZ,
    rappel_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Récurrence
    recurrence TEXT,  -- null, daily, weekly, monthly, cron:expression

    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,
    tags TEXT[] DEFAULT '{}',

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by TEXT DEFAULT 'jarvis'
);

-- ============================================================
-- TABLE 5 : file_humaine
-- Décisions à valider par Hamid (ou autre humain)
-- ============================================================
CREATE TABLE IF NOT EXISTS file_humaine (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Contexte de la décision
    contexte JSONB NOT NULL,
    -- Format : {"projet_id": "...", "contact_id": "...", "action": "envoyer_devis", "details": "..."}

    -- Proposition de Jarvis
    proposition TEXT NOT NULL,
    options JSONB,  -- choix possibles si applicable

    -- Urgence et catégorie
    urgence TEXT NOT NULL DEFAULT 'normale' CHECK (urgence IN ('bloquante', 'urgente', 'normale', 'info')),
    categorie TEXT,  -- commercial, financier, technique, rh, juridique, marketing
    persona TEXT,    -- quelle persona a généré cette demande

    -- Décision
    decision TEXT NOT NULL DEFAULT 'pending' CHECK (decision IN ('pending', 'approved', 'rejected', 'modified')),
    decision_comment TEXT,
    decision_meta JSONB,  -- {"decided_by": "hamid", "via": "pwa|whatsapp|telegram", "modified_value": "..."}

    -- Timing
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,  -- auto-approve ou escalade si pas répondu

    -- Audit
    created_by TEXT DEFAULT 'jarvis'
);

-- ============================================================
-- TABLE 6 : audit_logs (sécurité — module-securite-france)
-- Trace de toutes les actions Jarvis
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Qui
    actor TEXT NOT NULL,  -- jarvis, hamid, system, mcp:pennylane, etc.
    persona TEXT,         -- lea, claire, hugo...

    -- Quoi
    action TEXT NOT NULL,  -- create, update, delete, send_email, send_whatsapp, api_call, decision...
    resource_type TEXT,    -- contact, projet, document, tache, file_humaine
    resource_id UUID,

    -- Détails
    details JSONB DEFAULT '{}'::jsonb,
    -- Format : {"model": "opus", "tokens_in": 500, "tokens_out": 200, "mcp": "pennylane", "duration_ms": 1200}

    -- Résultat
    status TEXT DEFAULT 'success' CHECK (status IN ('success', 'error', 'warning')),
    error_message TEXT,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ip_address TEXT
);

-- ============================================================
-- Trigger auto-update updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER contacts_updated_at BEFORE UPDATE ON contacts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER projets_updated_at BEFORE UPDATE ON projets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER taches_updated_at BEFORE UPDATE ON taches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- Séquence pour références projets auto (ELX-2026-0001)
-- ============================================================
CREATE SEQUENCE IF NOT EXISTS projet_ref_seq START 1;

CREATE OR REPLACE FUNCTION generate_projet_reference()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.reference IS NULL THEN
        NEW.reference := 'ELX-' || to_char(now(), 'YYYY') || '-' || lpad(nextval('projet_ref_seq')::text, 4, '0');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER projets_auto_reference BEFORE INSERT ON projets
    FOR EACH ROW EXECUTE FUNCTION generate_projet_reference();
