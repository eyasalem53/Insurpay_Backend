from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from datetime import date, datetime
from typing import Any
import os
import re
import requests
import json

router = APIRouter(prefix="/agent", tags=["Agent LLM"])


class AgentRequest(BaseModel):
    question: str


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise HTTPException(
            status_code=500,
            detail="DATABASE_URL introuvable dans le fichier .env.",
        )

    return database_url


def get_engine() -> Engine:
    return create_engine(get_database_url())
def get_ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def get_ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", "qwen3:14b")

def normalize_text(value: str | None) -> str:
    if not value:
        return ""

    return (
        value.lower()
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("à", "a")
        .replace("ù", "u")
        .replace("ç", "c")
        .replace("’", "'")
        .strip()
    )


def format_date(value: Any) -> str:
    if value is None:
        return "Non renseignée"

    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")

    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")

    return str(value)


def build_anomaly_description(
    libelle: str,
    domaine: str,
    code: str,
    nombre_repetitions: int,
    premiere_detection: Any,
    derniere_detection: Any,
) -> str:
    code_normalized = normalize_text(code)

    descriptions = {
        "contrat_clos_date_future": (
            "Le contrat est clôturé avec une date de clôture située dans le futur. "
            "Cette incohérence doit être vérifiée avant exploitation."
        ),
        "ventil_absente": (
            "Le contrat est ouvert mais aucune ventilation technique active n’est associée. "
            "La répartition technique du contrat est donc incomplète."
        ),
        "cotis_manquante": (
            "Une cotisation attendue est absente pour ce contrat. "
            "Cela peut provoquer un écart dans le montant à prélever."
        ),
        "ventil_double": (
            "Le contrat présente une ventilation technique en double. "
            "Cette anomalie peut créer des incohérences dans la répartition technique du contrat."
        ),
        "contrat_ouvert_motif_cloture": (
            "Le contrat est ouvert mais un motif de clôture est renseigné. "
            "Cette situation indique une incohérence entre le statut du contrat et les informations de clôture."
        ),
        "rum_invalide": (
            "Le mandat RUM associé au contrat est invalide ou non exploitable. "
            
        ),
        "version_iban_invalide": (
            "La version du contrat contient un IBAN absent, invalide ou clôturé. "
            "Cette situation bloque la fiabilité du prélèvement bancaire."
        ),
        "sans_echeancier": (
            "Le contrat est ouvert mais aucun échéancier valide n’est associé. "
            "Le cycle de prélèvement ne peut pas être correctement préparé."
        ),
        "cotis_apres_cloture": (
            "Des cotisations sont présentes après la date de clôture du contrat. "
            "Cela indique une incohérence entre le statut du contrat et les mouvements financiers."
        ),
        "rejets_eleves": (
            "Le contrat présente un nombre élevé de rejets de prélèvement. "
            "Cela indique un risque bancaire important."
        ),
        "contrat_clos_sans_date_cloture": (
            "Le contrat est clôturé mais aucune date de clôture n’est renseignée. "
            "Le statut contractuel est donc incomplet."
        ),
        "contrat_clos_sans_raison_cloture": (
            "Le contrat est clôturé sans motif de clôture. "
            "Cette information est nécessaire pour assurer la traçabilité métier."
        ),
        "contrat_ouvert_date_cloture_depassee": (
            "Le contrat est encore ouvert alors que sa date de clôture est dépassée. "
            "Le statut du contrat doit être régularisé."
        ),
        "contrat_cloture_closed_by_vide": (
            "Le champ indiquant l’utilisateur ou l’origine de la clôture est vide. "
            "Cela réduit la traçabilité de l’opération."
        ),
        "jour_prelevement_non_conforme": (
            "Le jour de prélèvement renseigné ne respecte pas les jours autorisés. "
            "Cette situation peut provoquer une mauvaise planification du prélèvement."
        ),
        "cotis_avant_effet": (
            "Des cotisations sont présentes avant la date d’effet du contrat. "
            "Cela peut indiquer une erreur de génération ou d’affectation des mouvements."
        ),
        "version_double": (
            "Le contrat présente une version dupliquée. "
            "Cela peut créer des incohérences dans l’historique contractuel."
        ),
        "frais_dossier_manquants": (
            "Les frais de dossier attendus ne sont pas correctement comptabilisés. "
            "Le montant total du contrat peut être incomplet."
        ),
        "cotis_double": (
            "Des cotisations semblent être comptabilisées en double. "
            "Cette anomalie peut fausser les montants à prélever."
        ),
        "souscripteur_iban_invalide": (
            "Le souscripteur ne possède pas d’IBAN valide ou exploitable. "
            "Cette anomalie peut empêcher le prélèvement."
        ),
        "iban_invalide": (
            "Les informations bancaires du contrat sont invalides ou non exploitables. "
            "Cela peut entraîner un rejet du prélèvement."
        ),
    }

    base_description = descriptions.get(
        code_normalized,
        f"{libelle}. Cette anomalie appartient au domaine {domaine} et nécessite une vérification métier.",
    )

    return (
        f"{base_description} "
        f"Elle a été détectée {nombre_repetitions} fois pour ce contrat. "
        f"Première détection : {format_date(premiere_detection)}. "
        f"Dernière détection : {format_date(derniere_detection)}."
    )


def fetch_contract_info(numero_contrat: str) -> dict:
    engine = get_engine()

    query = text(
        """
        SELECT
            c.id_contrat,
            c.numero_contrat,
            c.statut,
            c.date_effet,
            c.date_creation,
            c.date_cloture,
            c.motif_cloture,
            c.id_gestionnaire,
            c.id_assureur,
            c.id_courtier,
            c.id_gamme,
            c.date_chargement
        FROM public.dim_contrat AS c
        WHERE CAST(c.id_contrat AS TEXT) = :numero_contrat
           OR CAST(c.numero_contrat AS TEXT) = :numero_contrat
        LIMIT 1
        """
    )

    try:
        with engine.connect() as connection:
            row = connection.execute(
                query,
                {"numero_contrat": numero_contrat},
            ).mappings().first()

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la lecture du contrat : {str(error)}",
        )

    if not row:
        return {}

    return {
        "id_contrat": row["id_contrat"],
        "numero_contrat": row["numero_contrat"],
        "statut": row["statut"] or "Non renseigné",
        "date_effet": format_date(row["date_effet"]),
        "date_creation": format_date(row["date_creation"]),
        "date_cloture": format_date(row["date_cloture"]),
        "motif_cloture": row["motif_cloture"] or "Non renseigné",
        "id_gestionnaire": row["id_gestionnaire"],
        "id_assureur": row["id_assureur"],
        "id_courtier": row["id_courtier"],
        "id_gamme": row["id_gamme"],
        "date_chargement": format_date(row["date_chargement"]),
    }


def fetch_contract_anomalies(numero_contrat: str) -> list[dict]:
    engine = get_engine()

    query = text(
        """
        SELECT
            f.id_type_anomalie,
            ta.nom_anomalie AS libelle,
            ta.domaine AS domaine,
            ta.criticite AS criticite,
            ta.code AS code,
            COUNT(*) AS nombre_repetitions,
            MIN(d.date_complete) AS premiere_detection,
            MAX(d.date_complete) AS derniere_detection
        FROM public.fact_anomalie_prelevement AS f
        LEFT JOIN public.dim_contrat AS c
            ON c.id_contrat = f.id_contrat
        LEFT JOIN public.dim_type_anomalie AS ta
            ON ta.id_type_anomalie = f.id_type_anomalie
        LEFT JOIN public.dim_date AS d
            ON d.id_date = f.id_date
        WHERE CAST(f.id_contrat AS TEXT) = :numero_contrat
           OR CAST(c.numero_contrat AS TEXT) = :numero_contrat
        GROUP BY
            f.id_type_anomalie,
            ta.nom_anomalie,
            ta.domaine,
            ta.criticite,
            ta.code
        ORDER BY
            MAX(d.date_complete) DESC NULLS LAST,
            f.id_type_anomalie ASC
        """
    )

    try:
        with engine.connect() as connection:
            rows = connection.execute(
                query,
                {"numero_contrat": numero_contrat},
            ).mappings().all()

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la lecture des anomalies : {str(error)}",
        )

    anomalies = []

    for row in rows:
        libelle = row["libelle"] or "Anomalie détectée"
        domaine = row["domaine"] or "Non classé"
        criticite = row["criticite"] or "Moyenne"
        code = row["code"] or "NON_RENSEIGNE"
        nombre_repetitions = int(row["nombre_repetitions"] or 1)

        anomalies.append(
            {
                "libelle": libelle,
                "domaine": domaine,
                "criticite": criticite,
                "date_detection": format_date(row["derniere_detection"]),
                "description": build_anomaly_description(
                    libelle=libelle,
                    domaine=domaine,
                    code=code,
                    nombre_repetitions=nombre_repetitions,
                    premiere_detection=row["premiere_detection"],
                    derniere_detection=row["derniere_detection"],
                ),
                "nombre_repetitions": nombre_repetitions,
                "code": code,
            }
        )

    return anomalies

def calculate_decision(anomalies: list[dict]) -> str:
    if not anomalies:
        return "OK"

    criticites = [normalize_text(anomaly.get("criticite")) for anomaly in anomalies]

    has_high = any(
        criticite in ["elevee", "haute", "high"]
        for criticite in criticites
    )

    has_medium = any(
        criticite in ["moyenne", "medium"]
        for criticite in criticites
    )

    if has_high:
        return "KO"

    if has_medium:
        return "SUSPECT"

    return "SUSPECT"


def build_explanation(numero_contrat: str, decision: str, anomalies: list[dict]) -> str:
    if not anomalies:
        return (
            f"Le contrat {numero_contrat} ne présente aucune anomalie détectée "
            "dans le Data Warehouse pour le périmètre de contrôle actuel. "
            "La décision automatique calculée est : OK."
        )

    total_types = len(anomalies)
    total_repetitions = sum(
        int(anomaly.get("nombre_repetitions", 1))
        for anomaly in anomalies
    )

    domaines = sorted(
        {
            anomaly.get("domaine", "Non classé")
            for anomaly in anomalies
            if anomaly.get("domaine")
        }
    )

    criticites = sorted(
        {
            anomaly.get("criticite", "Moyenne")
            for anomaly in anomalies
            if anomaly.get("criticite")
        }
    )

    return (
        f"Le contrat {numero_contrat} présente {total_types} type(s) d’anomalie détecté(s), "
        f"avec un total de {total_repetitions} occurrence(s). "
        f"Les domaines concernés sont : {', '.join(domaines)}. "
        f"Les niveaux de criticité issus du référentiel sont : {', '.join(criticites)}. "
        f"La décision automatique calculée pour ce contrat est : {decision}."
    )


def build_recommendation(decision: str, anomalies: list[dict]) -> str:
    if not anomalies:
        return (
            "Aucune action corrective immédiate n’est nécessaire. "
            "Le contrat peut rester dans le suivi normal."
        )

    codes = {normalize_text(anomaly.get("code", "")) for anomaly in anomalies}
    domaines = {normalize_text(anomaly.get("domaine", "")) for anomaly in anomalies}

    actions = []

    if (
        "iban_invalide" in codes
        or "version_iban_invalide" in codes
        or "souscripteur_iban_invalide" in codes
    ):
        actions.append("vérifier et corriger les informations IBAN du contrat ou du souscripteur")

    if "rum_invalide" in codes:
        actions.append("contrôler le mandat RUM et régulariser les données SEPA")

    if "rejets_eleves" in codes:
        actions.append("analyser l’historique des rejets et contacter le souscripteur si nécessaire")

    if "sans_echeancier" in codes:
        actions.append("créer ou corriger l’échéancier associé au contrat")

    if "jour_prelevement_non_conforme" in codes:
        actions.append("corriger le jour de prélèvement selon les jours autorisés")

    if "ventil_double" in codes:
        actions.append("identifier et supprimer les ventilations techniques en double")

    if "ventil_absente" in codes:
        actions.append("ajouter ou activer une ventilation technique valide")

    if "cotis_double" in codes:
        actions.append("contrôler les cotisations en double et corriger les montants concernés")

    if "cotis_manquante" in codes:
        actions.append("vérifier les cotisations manquantes et compléter les mouvements attendus")

    if "cotis_apres_cloture" in codes:
        actions.append("annuler ou corriger les cotisations générées après la date de clôture")

    if "cotis_avant_effet" in codes:
        actions.append("vérifier les cotisations générées avant la date d’effet du contrat")

    if "frais_dossier_manquants" in codes:
        actions.append("contrôler la comptabilisation des frais de dossier")

    if (
        "contrat_clos_date_future" in codes
        or "contrat_clos_sans_date_cloture" in codes
        or "contrat_clos_sans_raison_cloture" in codes
        or "contrat_ouvert_date_cloture_depassee" in codes
        or "contrat_cloture_closed_by_vide" in codes
        or "contrat_ouvert_motif_cloture" in codes
    ):
        actions.append("régulariser les informations de clôture et le statut du contrat")

    if "version_double" in codes:
        actions.append("contrôler les versions du contrat et supprimer les doublons incohérents")

    if not actions:
        if "bancaire" in domaines:
            actions.append("vérifier les données bancaires liées au contrat")
        if "cotisation" in domaines:
            actions.append("contrôler les cotisations et les mouvements financiers")
        if "ventilation" in domaines:
            actions.append("contrôler les ventilations techniques du contrat")
        if "contractuel" in domaines or "contrat" in domaines:
            actions.append("vérifier les informations contractuelles")
        if not actions:
            actions.append("analyser les anomalies détectées et corriger les données concernées")

    if decision == "KO":
        prefix = "Bloquer temporairement le prélèvement, puis "
    elif decision == "SUSPECT":
        prefix = "Mettre le contrat en vérification avant prélèvement, puis "
    else:
        prefix = "Valider le contrat après contrôle simple, puis "

    return prefix + "; ".join(actions) + "."

def build_llm_prompt(
    numero_contrat: str,
    contract_info: dict,
    anomalies: list[dict],
    decision: str,
) -> str:
    safe_payload = {
        "numero_contrat": numero_contrat,
        "decision_automatique": decision,
        "contrat": contract_info,
        "anomalies": anomalies,
    }

    return f"""
Tu es un assistant décisionnel professionnel intégré à une plateforme BI nommée InsurPay Analytics.

Contexte métier:
La plateforme analyse les anomalies de prélèvement avant exécution du prélèvement bancaire.
Les anomalies proviennent du Data Warehouse et ne doivent jamais être inventées.

Données disponibles au format JSON:
{json.dumps(safe_payload, ensure_ascii=False, indent=2)}

Ta mission:
Générer une réponse claire, professionnelle et courte en français.

Règles strictes:
- Ne modifie jamais la décision automatique.
- Ne crée jamais de nouvelle anomalie.
- N'invente jamais de date, montant, statut ou information absente.
- Si une information est absente, écris "Non renseigné".
- La décision doit rester exactement: {decision}
- Ne parle pas comme un chatbot généraliste.
- Ne montre jamais ton raisonnement interne.
- Réponds comme un assistant décisionnel métier.

Format obligatoire de réponse:

Résumé du contrat:
...

Analyse des anomalies:
...

Justification de la décision:
...

Recommandation métier:
...

Niveau de priorité:
...
""".strip()


def generate_llm_analysis(
    numero_contrat: str,
    contract_info: dict,
    anomalies: list[dict],
    decision: str,
) -> dict:
    prompt = build_llm_prompt(
        numero_contrat=numero_contrat,
        contract_info=contract_info,
        anomalies=anomalies,
        decision=decision,
    )

    url = f"{get_ollama_base_url()}/api/generate"

    payload = {
        "model": get_ollama_model(),
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
            "num_ctx": 4096,
            "num_predict": 700,
        },
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=(10, 300),  # 10s connection timeout, 300s generation timeout
        )

        response.raise_for_status()

        data = response.json()
        llm_response = data.get("response", "").strip()

        # Qwen3 can sometimes return internal thinking tags.
        # This removes them if they appear.
        llm_response = re.sub(
            r"<think>.*?</think>",
            "",
            llm_response,
            flags=re.DOTALL | re.IGNORECASE,
        ).strip()

        if not llm_response:
            raise ValueError("Réponse vide retournée par Ollama.")

        return {
            "llm_enabled": True,
            "model": get_ollama_model(),
            "analysis": llm_response,
            "error": "",
        }

    except requests.exceptions.Timeout:
        return {
            "llm_enabled": False,
            "model": get_ollama_model(),
            "analysis": "",
            "error": "Ollama a dépassé le délai de réponse. Le modèle est peut-être encore en chargement ou trop lent.",
        }

    except requests.exceptions.ConnectionError:
        return {
            "llm_enabled": False,
            "model": get_ollama_model(),
            "analysis": "",
            "error": "Connexion impossible à Ollama. Vérifiez OLLAMA_BASE_URL, le port 11434 et le firewall du serveur.",
        }

    except requests.exceptions.HTTPError as error:
        return {
            "llm_enabled": False,
            "model": get_ollama_model(),
            "analysis": "",
            "error": f"Erreur HTTP Ollama : {str(error)}",
        }

    except Exception as error:
        return {
            "llm_enabled": False,
            "model": get_ollama_model(),
            "analysis": "",
            "error": f"Ollama indisponible ou erreur de génération : {str(error)}",
        }
@router.post("/analyze-contract")
def analyze_contract(payload: AgentRequest):
    question = payload.question.strip()

    match = re.search(r"\d+", question)

    if not match:
        return {
            "success": False,
            "numero_contrat": "",
            "contrat": {},
            "decision": "",
            "anomalies": [],
            "explication": "",
            "recommandation": "Veuillez saisir un numéro de contrat valide.",
            "llm_enabled": False,
            "llm_model": get_ollama_model(),
            "llm_analysis": "",
        }

    numero_contrat = match.group(0)

    contract_info = fetch_contract_info(numero_contrat)
    anomalies = fetch_contract_anomalies(numero_contrat)
    decision = calculate_decision(anomalies)

    fallback_explication = build_explanation(numero_contrat, decision, anomalies)
    fallback_recommandation = build_recommendation(decision, anomalies)

    llm_result = generate_llm_analysis(
        numero_contrat=numero_contrat,
        contract_info=contract_info,
        anomalies=anomalies,
        decision=decision,
    )

    return {
        "success": True,
        "numero_contrat": numero_contrat,
        "contrat": contract_info,
        "decision": decision,
        "anomalies": anomalies,

        # Old fields kept for frontend compatibility
        "explication": fallback_explication,
        "recommandation": fallback_recommandation,

        # New Ollama fields
        "llm_enabled": llm_result.get("llm_enabled", False),
        "llm_model": llm_result.get("model", get_ollama_model()),
        "llm_analysis": llm_result.get("analysis", ""),
        "llm_error": llm_result.get("error", ""),
    }