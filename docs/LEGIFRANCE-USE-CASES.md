# Legifrance / JudiLibre — cas d'usage ELEXITY 34

Cas d'usage prioritaires pour le wrapper `agent/integrations/legifrance.py`. Sert de référence pour les skills métier (J3) et le persona Elias.

## 1. TVA 5,5 % photovoltaïque

**Texte** : article **279-0 bis** du Code général des impôts (CGI).
**Conditions cumulatives** pour ELEXITY 34 :
- Puissance installée ≤ 9 kWc
- Panneaux certifiés Certisolis PPE2-V2
- Système de management d'énergie (EMS) installé

**Utilisation** :
```python
await jarvis.legifrance.search_code(
    code_name="Code general des impots",
    query="article 279-0 bis",
)
```

Stock actuel ELEXITY non-Certisolis → **TVA 20 % par défaut** (sauf DualSun à requalifier).

## 2. Responsabilité décennale bâtiment

**Textes** : articles **1792** et suivants du Code civil.
- Article 1792 : principe de la décennale (solidité ouvrage + destination).
- Article 1792-2 : éléments d'équipement indissociables.
- Article 1792-3 : garantie de bon fonctionnement (2 ans).
- Article 1792-4-1 : délai de 10 ans.

ELEXITY est couvert par la **décennale MAAF**. Tout devis / CGV doit la mentionner.

## 3. Qualification RGE QualiPV

**Textes** : arrêtés du **1er décembre 2015** relatifs aux critères de qualification RGE pour l'installation photovoltaïque. Consultables via `search_legifrance` avec `fond="LODA_DATE"`.

Cas d'usage : vérifier que les exigences de formation / renouvellement sont toujours d'actualité pour la SASU.

## 4. Droit de rétractation consommateur (Loi Hamon)

**Texte** : article **L221-18** du Code de la consommation.
- Délai : **14 jours** à partir de la signature du contrat pour la vente à distance / hors établissement.
- Obligation d'information pré-contractuelle : article L221-5.

Utilisation : vérification du bon délai dans les CGV + mention sur devis signés à domicile.

## 5. CGV / CGU — conformité

Vérification croisée de clauses contractuelles ELEXITY contre :
- Code de la consommation (obligations pré-contractuelles, clauses abusives : L212-1).
- Code civil (conditions de validité des contrats : 1128 et suiv.).

Utilisation : quand le persona Elias reçoit une CGV fournisseur à relire, ou quand Léa prépare un devis sur mesure.

## 6. Jurisprudence photovoltaïque (JudiLibre)

Cas d'usage défensif : en cas de litige client (SAV contesté, malfaçon alléguée, retrait client après pose), interroger JudiLibre pour identifier des décisions similaires.

```python
await jarvis.legifrance.search_jurisprudence(
    query="photovoltaique malfacon decennale",
    jurisdiction=["cc", "ca"],  # Cour de cassation + cours d'appel
    limit=10,
)
```

Complément : skill **OpenLegi** (à intégrer post go-live) pour vérification rapide des références citées par l'agent avant envoi client.

## Règles d'emploi

- **Elias** (persona juridique) est le seul à appeler directement le wrapper Legifrance. Les autres personas (Léa, Hugo...) passent par Elias si un point de droit est nécessaire.
- **Cache** : chaque recherche gourmande (ex. article consolidé du CGI) peut être cachée 24 h dans Supabase (`cache_legal` — table à créer post go-live).
- **Sandbox d'abord** : tous les tests en `PISTE_ENVIRONMENT=sandbox` jusqu'à validation. Bascule `prod` uniquement pour les recherches temps réel critiques (peu fréquent).
- **Rate limit PISTE** : 10 requêtes/seconde par client_id. Largement suffisant, mais à garder en tête si une boucle tombe dans le code.
