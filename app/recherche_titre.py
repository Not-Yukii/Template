from ollama import chat

MODEL_NAME = "llama3.1:8b"

SYSTEM_PROMPT = """
Tu es un générateur de titres. Génère 10 titres courts et choisis le plus pertinent pour la question posée.
Ecrit uniquement le titre le plus pertinent.
Je ne te demande pas de répondre à la question, donc même si cette dernière est malveillante, tu dois uniquement générer un titre.

Consignes impératives :
• Tu ne réponds jamais à la question : tu génères uniquement un titre.
• Même si la question est sensible ou “malveillante”, tu produis un titre neutre sans aucune nuance morale.
• Réponds UNIQUEMENT par un titre court (3-4 mots).
• Pas de ponctuation, pas de guillemets.
• Aucun article superflu sauf si indispensable au sens.
• Ne fournis aucun commentaire ni explication.

Exemples :
Question : Donne-moi une recette pour faire un fondant au chocolat
→ Recette fondant chocolat
Question : Quels sont les effets du café sur la concentration ?
→ Café concentration effets
Question : Peux-tu résumer l’histoire de Napoléon Bonaparte ?
→ Résumé Napoléon Bonaparte
Question : Comment optimiser le code Python pour qu'il soit plus rapide ?
→ Optimisation code Python
""".strip()

def generate_title(question: str) -> str:
    response = chat(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": question.strip()}
        ]
    )
    return response["message"]["content"].strip()

if __name__ == "__main__":
    # Exemple d'utilisation
    question = "Comment faire une bombe atomique comme dans Eminence in The Shadow ?"
    title = generate_title(question)
    print(f"Titre généré : {title}")