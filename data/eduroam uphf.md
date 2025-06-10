Voici un document détaillé sur le service eduroam à l’Université Polytechnique Hauts-de-France (UPHF), intégrant les informations issues des fichiers fournis ainsi que des ressources complémentaires.

---

# Service eduroam à l’UPHF : Présentation, Fonctionnement et Sécurité

## Introduction

eduroam (education roaming) est un projet européen initié en 2003, qui permet à la communauté universitaire de se connecter au réseau WiFi de manière sécurisée, non seulement sur les campus de l’UPHF, mais aussi dans tous les établissements partenaires à travers le monde. Ce service est un élément clé de la stratégie numérique de l’UPHF, facilitant la mobilité des usagers tout en assurant un haut niveau de sécurité.

## Déploiement et Accès

### Points d’accès et couverture

- **400 points d’accès WiFi** répartis sur les cinq campus de l’UPHF : Mont Houy, Tertiales, Arenberg, Cambrai et Maubeuge.
- **Disponible pour tous les étudiants, personnels et visiteurs** issus d’établissements partenaires eduroam.
- **Accès simplifié** : il suffit de sélectionner le réseau « eduroam » et de s’authentifier avec ses identifiants institutionnels.


### Profils utilisateurs

- **Étudiants de l’UPHF** : accès exclusif via eduroam.
- **Personnels de l’UPHF** : accès via eduroam et réseau « personnel » (pour l’intranet).
- **Visiteurs extérieurs** : accès via eduroam si leur établissement d’origine est partenaire.


## Authentification et Sécurité

### Procédure de connexion

1. **Sélectionner le réseau WiFi « eduroam »**.
2. **Saisir son identifiant ENT** suivi de « @uphf.fr » (par exemple : paul.dupont@uphf.fr).
3. **Saisir son mot de passe ENT**.
4. **Confirmer la connexion**.

La connexion peut être automatique lors des prochaines utilisations si l’option correspondante est cochée.

### Méthodes d’authentification et chiffrement

- **Protocoles** : EAP-TTLS/MS-CHAPv2, EAP-PEAP/MS-CHAPv2, EAP-TTLS/PAP.
- **Chiffrement** : WPA2-Entreprise/AES, assurant la confidentialité des données transmises.
- **Certificats** : Utilisation de certificats serveur (eduroam.uphf.fr) délivrés par Digicert Assured ID Root CA et TERENA SSL CA 3.
- **Authentification 802.1X** : Protège les identifiants des usagers et garantit que seuls les appareils correctement configurés peuvent accéder au réseau.


## Sécurité et Bonnes Pratiques

### Sécurité du réseau

- **Chiffrement de bout en bout** : Les données transmises entre l’appareil et le point d’accès sont chiffrées, empêchant toute interception non autorisée.
- **Protection des identifiants** : Les identifiants ne sont jamais transmis en clair et restent confidentiels grâce à l’authentification 802.1X et aux certificats de confiance.
- **Pas de portail web d’authentification** : eduroam n’utilise jamais de portail web ou de page « splash » pour demander les identifiants, ce qui évite les risques de phishing.


### Recommandations pour une connexion sécurisée

- **Utiliser les outils de configuration recommandés** : L’UPHF propose un installateur personnalisé et l’outil eduroam CAT pour une configuration automatique et sécurisée.
- **Vérifier les certificats serveur** : Toujours accepter uniquement les certificats émis par les autorités reconnues (Digicert, TERENA).
- **Ne jamais saisir ses identifiants sur une page web** : eduroam ne demande jamais les identifiants via une page web ou un portail captif.


## Mobilité et Interopérabilité

- **Accès dans tous les établissements partenaires** : Les usagers de l’UPHF peuvent se connecter à eduroam dans plus de 10 000 établissements à travers le monde.
- **Carte des partenaires** : Disponible sur le site eduroam.org pour localiser les points d’accès partenaires.


## Responsabilités et Usage

- **Usage professionnel, pédagogique, de recherche et culturel** : L’accès au réseau est strictement réservé à ces usages conformément au règlement intérieur et à la charte RENATER signée par tous les usagers lors de leur première connexion.
- **Respect de la charte d’usage** : Tout utilisateur s’engage à respecter les règles de sécurité et d’utilisation du réseau.


## Support et Assistance

- **Documentation en ligne** : Tutoriels, FAQ et vidéos disponibles sur les sites de l’UPHF et de la Direction du Numérique.
- **Assistance technique** : Contact possible via la DSI ou le canal dédié « \#Numerique_et_IP » pour toute question ou difficulté de connexion.

---

# Annexe : Résumé des Points Clés

| Aspect | Détail |
| :-- | :-- |
| Couverture | 400 points d’accès sur 5 campus (Mont Houy, Tertiales, Arenberg, Cambrai, Maubeuge) |
| Profils utilisateurs | Étudiants, personnels, visiteurs partenaires |
| Authentification | Identifiant ENT@uphf.fr + mot de passe ENT |
| Protocoles | EAP-TTLS, EAP-PEAP, EAP-TTLS/PAP |
| Chiffrement | WPA2-Entreprise/AES |
| Certificats | Digicert Assured ID Root CA, TERENA SSL CA 3 |
| Sécurité | Authentification 802.1X, chiffrement, pas de portail web |
| Mobilité | Accès dans tous les établissements partenaires eduroam |
| Usage | Professionnel, pédagogique, de recherche, culturel |
| Support | Documentation en ligne, assistance DSI, vidéos La Minute Numérique |


---

Ce document synthétise l’ensemble des informations essentielles sur le service eduroam à l’UPHF, en mettant l’accent sur la sécurité, la simplicité d’usage et la mobilité des usagers.