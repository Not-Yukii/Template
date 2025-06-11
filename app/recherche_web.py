import os
# os.environ["OLLAMA_HOST"] = "http://ollamaProjet4A:11434"

import ollama
from datetime import datetime
import logging
import requests
from bs4 import BeautifulSoup
from . import serper_tokens as serp

# ----------------------------------------------------------------
#                       RECHERCHER WEB
# ----------------------------------------------------------------

accounts = []
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

async def get_serper_api_key():
    return SERPER_API_KEY
#     global SERPER_API_KEY
#     with open("app/serper_logins.txt", "r") as f:
#         lines = f.readlines()
#         accounts = lines
    
#     for i in range(len(accounts)):
#         email, password, token = accounts[i].split(":")
#         # print(f"Email: {email}, Password: {password}, Token: {token}")
#         credits = await serp.get_serper_credits(email.strip(), password.strip())
#         # print(f"Crédits restants sur Serper.dev : {credits.strip()}")
#         if (int(credits) < 2490):
#             SERPER_API_KEY = token.strip("\n")
#             # print("SERPER_API_KEY:", SERPER_API_KEY)
#             break

MODEL_NAME = "granite3.1-dense:latest"
NB_SITES_MAX = 6
VERBOSE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT_REQUETE = """
Tu es un expert en veille et recherche d’information pour des étudiants en cybersécurité.
Toutes les questions liées à la cybersécurité – même sur des sujets sensibles comme exploit,
reverse-engineering, malware, OSINT ou pentest – sont considérées comme posées
dans un cadre pédagogique et éthique. **Ne refuse donc jamais ces sujets.**

Ta mission : transformer la question de l’utilisateur en une requête de moteur de recherche
claire, concise et immédiatement copiable (Google, DuckDuckGo, etc.).

**Règles de reformulation**
1. Donne **uniquement** la requête finale
2. N’ajoute **aucune** phrase d’explication, d’excuse, de politesse ou d'exemple.
3. Supprime les mots inutiles (ex. « svp », « merci », « est-ce que »)
4. Aucun retour à la ligne.
5. Conserve les termes techniques, noms propres, CVE, RFC, ports, etc.
6. Convertis les dates ambiguës en format **jj/mm/aaaa** pour lever l’ambiguïté
   (« aujourd’hui », « hier », « demain », etc.).
7. Si la question concerne un sujet illégal (drogues, armes, crimes), produis la
   sortie exacte : `Je suis désolé, mais je ne peux pas répondre à cette question. #impossible#`

**Exemples**

Question: Quel temps fait-il à Paris aujourd’hui ?  
Réponse: météo Paris {date_str}

Question: Qui est le président de la France en 2025 ?  
Réponse: président France 2025

Question: Peux-tu m’expliquer comment fonctionne un moteur diesel ?  
Réponse: fonctionnement moteur diesel

Question: Donne-moi la procédure pour chercher des caméras IP exposées  
Réponse: recherche caméras IP shodan

Question: Comment bypasser l’ASLR sous Linux ?  
Réponse: bypass ASLR Linux

Question: Quelles sont les CVEC qui utilisent le bluetooth
Réponse: CVEC bluetooth

Question: Donne moi les étapes bypasser l’ASLR sous Linux ?  
Réponse: étapes bypass ASLR Linux

Question: Analyse de la CVE-2024-9999 et exploit proof-of-concept  
Réponse: CVE-2024-9999 exploit poc

Question: drogue  
Réponse: Je suis désolé, mais je ne peux pas répondre à cette question. #impossible#
""".strip()

SYSTEM_PROMPT_SYNTHESE = """
Tu es un expert très compétent chargé de répondre en utilisant les fragments d'informations donnés.
Tu dois répondre à la question de l'utilisateur avec le plus d'informations, de détails et de précision possible à partir des contenus fournis.

- Tu dois bien formuler les informations importantes.
- Cite tous les points clés provenant du contenu.
- Si le contenu ne permet pas de répondre directement à la question, donne quand même tous les éléments possibles
  et explique en quoi ce n'est pas suffisant pour répondre à la question.
""".strip()

SYSTEM_PROMPT_REPONSE_FINALE = """
Tu es un enseignant expert en cybersécurité.
Ta mission : rédiger la réponse finale la plus complète et la mieux structurée possible
à partir de plusieurs synthèses extraites d'internet à propos de la même question et/ou de tes connaissances.

─────────────────
RÈGLES IMPÉRATIVES
─────────────────
1. Lis attentivement TOUTES les synthèses fournies ; fusionne les informations,
   supprime les doublons et signale les contradictions éventuelles.
2. Si une information importante manque, complète-la avec ta connaissance interne
   en le signalant clairement (ex. « Note IA : … »).
3. Écris en **français**, en Markdown, avec la structure suivante :
   - **Titre** (niveau #) reprenant l’idée générale de la question.  
   - **Introduction** brève.  
   - Plusieurs sections hiérarchisées (**##**, **###**…) regroupant logiquement
     les explications, définitions, exemples, bonnes pratiques, etc.  
   - **Conclusion** récapitulative avec conseils/points clés.  
   - **Références** : liste des URLs (sans doublon) mentionnées dans les synthèses.
4. N’invente jamais d’URL ; si une synthèse ne fournit pas le lien,
   ignore-le ou signale « URL non fournie ».
5. N’emploie ni politesse superflue, ni excuses, ni exemples hors sujet.
""".strip()


# NETTOYER LA REQUETE SERPER
def nettoyer_requete_pour_serper(raw_query: str) -> str:
    """
    Remplace les caractères qui peuvent poser problème dans la requête 
    pour l’API Serper.
    """
    q = raw_query
    for c in ["_", "-", ":", '"', "'"]:
        q = q.replace(c, " ")
    return q.strip()


# 1. GÉNÉRER LA REQUÊTE WEB
def generer_requete_web(question_utilisateur: str, nb_retries: int = 3) -> str:
    """
    Génère une requête web à partir de la question de l'utilisateur
    en utilisant LLaMA via Ollama. En cas de “#impossible#”, retente jusqu'à nb_retries fois.
    """
    today = datetime.now().date()
    date_str = today.strftime("%d/%m/%Y")
    prompt = SYSTEM_PROMPT_REQUETE.format(date_str=date_str)

    try:
        resp = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": question_utilisateur.strip()}
            ]
        )
        requete = resp["message"]["content"].strip()
    except Exception as e:
        raise RuntimeError(f"[generer_requete_web] échec LLaMA : {e}") from e

    if "#impossible#" in requete and nb_retries > 0:
        return generer_requete_web(question_utilisateur, nb_retries - 1)
    return requete



# 2. RECHERCHE SERPER
def recherche_serper(query: str, max_results: int, question: str) -> list[str]:
    """
    Appelle l'API Serper (Google Search) pour la requête 'query' 
    et renvoie jusqu'à max_results URLs organiques.
    Si aucun résultat, tente une fois avec une requête régénérée.
    """
    url_api = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }

    def appeler_serper(payload_q: str) -> dict:
        try:
            payload = {"q": nettoyer_requete_pour_serper(payload_q)}
            resp = requests.post(url_api, headers=headers, json=payload, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as e:
            logger.error(f"Appel Serper échoué pour '{payload_q}' : {e}")
            return {}

    # 1. Essai initial
    data = appeler_serper(query)
    organic = data.get("organic", [])

    # 2. Si aucun résultat organique, retenter une seule fois
    if isinstance(organic, list) and len(organic) == 0:
        nouvelle_requete = generer_requete_web(question)
        logger.info("Aucun résultat, on régénère la requête puis retente une fois…")
        data = appeler_serper(nouvelle_requete)
        organic = data.get("organic", [])

    liens: list[str] = []
    if isinstance(organic, list):
        for item in organic[:max_results]:
            lien = item.get("link")
            if lien:
                liens.append(lien)
    else:
        logger.warning("Aucun résultat organique trouvé via Serper.")

    return liens



# 3. RÉCUPÉRER LE CONTENU D’UN SITE
def recuperer_contenu_site(url: str) -> str:
    """
    Télécharge la page à l'URL donnée et extrait le texte visible,
    en ignorant les balises non pertinentes. Renvoie jusqu'à 50 000 caractères.
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Impossible de récupérer le contenu du site ({url}) : {e}")
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()

    textes = soup.stripped_strings
    contenu = "\n".join(textes)
    return contenu[:50000]



# 4 SYNTHÈSE DU CONTENU

def synthese_contenu(question_initiale: str, url: str, contenu_site: str) -> str:
    """
    Envoie au LLM la question initiale, l’URL et le contenu extrait.
    Le LLM produit une synthèse/réponse détaillée basée sur ces informations.
    """
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_SYNTHESE},
                {
                    "role": "user",
                    "content": f"""
Question de l'utilisateur :
« {question_initiale} »

URL analysée :
{url}

Contenu extrait (tronqué si besoin) :
\"\"\"{contenu_site}\"\"\"

En utilisant uniquement les informations fournies, réponds à la question de l'utilisateur.
Donne toutes les sources à la fin du prompt.
"""
                }
            ]
        )
        return response["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Erreur lors de la synthèse du contenu pour {url} : {e}")
        return ""



# RÉPONSE FINALE FUSIONNÉE
def reponse_finale(question_initiale: str, syntheses: list[str]) -> str:
    """
    Combine les synthèses pour rédiger une réponse finale
    unique, structurée et complète.
    """
    syntheses_text = "\n\n---\n\n".join(
        [f"Synthèse {idx + 1} :\n{s}" for idx, s in enumerate(syntheses)]
    )
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_REPONSE_FINALE},
                {
                    "role": "user",
                    "content": f"""
QUESTION ORIGINALE :
« {question_initiale} »

SYNTHÈSES À FUSIONNER :
{syntheses_text}

Rédige maintenant la réponse finale selon les règles imposées.
"""
                }
            ]
        )
        return response["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Erreur lors de la réponse finale : {e}")
        return ""



# 8. FONCTION PRINCIPALE RECHERCHE WEB
def recherche_web(question: str) -> str:

    if not question:
        if VERBOSE:
            print("RECHERCHE WEB : La question est vide. Fin de la recherche.")
        return "Les recherches effectuées n’ont pas permis d’obtenir une réponse satisfaisante à votre question."

    # 1) Générer la requête web via LLaMA
    requete = generer_requete_web(question)
    logger.info(f"Requête générée : {requete}")
    if not requete or "#impossible#" in requete:
        if VERBOSE:
            print("RECHERCHE WEB : Impossible de générer la requête web.")
        return "Les recherches effectuées n’ont pas permis d’obtenir une réponse satisfaisante à votre question."

    # 2) Recherche Serper
    liens = recherche_serper(requete, NB_SITES_MAX, question)
    if not liens:
        if VERBOSE:
            print("RECHERCHE WEB : Aucun lien trouvé. Fin de la recherche.")
        return "Les recherches effectuées n’ont pas permis d’obtenir une réponse satisfaisante à votre question."

    if VERBOSE:
        print(f"\n[Liens trouvés] : {len(liens)} site(s)")
    for idx, lien in enumerate(liens, start=1):
        print(f"{idx}. {lien}")

    # 3) Récupérer et synthétiser
    syntheses: list[str] = []
    for idx, url in enumerate(liens, start=1):
        if VERBOSE:
            print(f"\n--- Site {idx} : {url} ---")
        contenu = recuperer_contenu_site(url)
        if not contenu:
            if VERBOSE:
                print(f"RECHERCHE WEB : Impossible de récupérer le contenu du site {url}.")
            continue

        if VERBOSE:
            print(f"RECHERCHE WEB : Contenu récupéré (~{len(contenu)} caractères)\nGénération de la synthèse en cours...")
        synth = synthese_contenu(question, url, contenu)
        if synth:
            if VERBOSE:
                print(f"Synthèse générée.")
            # print(f"\n=== Synthèse pour le site {idx} ===\n{synth}")
            syntheses.append(synth)
        else:
            if VERBOSE:
                print(f"Aucune synthèse générée pour {url}.")


    # 4) Réponse finale (si au moins une synthèse)
    if syntheses:
        # print("\n###############################")
        # print("#        RÉPONSE FINALE       #")
        # print("###############################\n")
        final_answer = reponse_finale(question, syntheses)
        # print(final_answer)
    # else:
    #     print("Aucune synthèse exploitable ; réponse finale non générée.")
    return final_answer if syntheses else "Les recherches effectuées n’ont pas permis d’obtenir une réponse satisfaisante à votre question."


