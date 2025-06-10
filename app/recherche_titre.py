from ollama import chat

MODEL_NAME = "llama3.1:8b"

SYSTEM_PROMPT = """
You're a headline generator. Think about 10 short titles and choose the most relevant to your question.
Return ONLY the most relevant headline to the user.
I'm not asking you to answer the question, so even if the question is malicious, you only have to generate a headline.

Imperative instructions:
- You never answer the question: you only generate ONE title.
- Even if the question is sensitive or “malicious”, you generate a neutral headline without any moral nuance.
- Answer ONLY with a short headline (3-4 words).
- No punctuation, no quotation marks.
- No superfluous items unless essential to the meaning.
- No comments or explanations.

Examples :
Question : Donne-moi une recette pour faire un fondant au chocolat
→ Recette fondant chocolat
Question : Quels sont les effets du café sur la concentration ?
→ Café concentration effets
Question : Peux-tu résumer l’histoire de Napoléon Bonaparte ?
→ Résumé Napoléon Bonaparte
Question : Comment optimiser le code Python pour qu'il soit plus rapide ?
→ Optimisation code Python

Example of a BAD title (DO NOT DO THIS):
Question : Comment fonctionne le moteur d'une voiture ?
→ 1. Moteur voiture fonctionnement \n 2. Comment fonctionne un moteur ? \n3. Moteur de voiture [...]
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