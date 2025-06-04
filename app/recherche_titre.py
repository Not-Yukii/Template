from ollama import chat

prompt = """
Tu es spécialisé dans la génération de titres.

Ta tâche est simple : à partir d'une question ou d'une requête utilisateur, génère un **titre court, clair et pertinent** qui résume l’essentiel du sujet.

- Ne réponds qu'avec le titre, sans explications ni commentaires
- Le titre doit être le plus concis possible (4 à 8 mots).
- Il ne doit contenir **aucun article inutile** ("le", "la", "un", "une", etc.) sauf si nécessaire au sens.
- Il doit être **représentatif du contenu** de la question.
- Il ne doit **jamais inclure de ponctuation** (pas de point, virgule, point d'interrogation, etc.).
- Il ne doit **rien ajouter ni reformuler** en dehors du titre.
- Retourne **uniquement** le titre. Aucune phrase explicative, aucun commentaire.

Exemples :

Utilisateur : Donne-moi une recette pour faire un fondant au chocolat  
Titre : Recette fondant chocolat

Utilisateur : Quels sont les effets du café sur la concentration ?  
Titre : Café concentration effets

Utilisateur : Comment fonctionne un moteur électrique ?  
Titre : Fonctionnement moteur électrique

Utilisateur : Est-ce que l’IA peut remplacer un médecin ?  
Titre : IA remplacement médecin

Utilisateur : Peux-tu me résumer l'histoire de Napoléon Bonaparte ?  
Titre : Résumé Napoléon Bonaparte

Maintenant, génère un titre pour cette question :
« {{QUESTION_UTILISATEUR}} »

"""

def generate_titre(content: str) -> str:
    response = chat(
        model="granite3.1-dense:8b",
        messages=[
            {"role": "user", "content": prompt.format(content=content)}
        ]
    )
    return response["message"]["content"]


# Exemple d'utilisation
if __name__ == "__main__":
    question = "Comment optimiser le code Python pour qu'il soit plus rapide ?"
    titre = generate_titre(question)
    print(f"Titre généré : {titre}")