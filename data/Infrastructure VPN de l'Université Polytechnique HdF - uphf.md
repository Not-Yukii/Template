
# Infrastructure VPN de l'Université Polytechnique Hauts-de-France : Analyse Technique et Fonctionnelle

L'Université Polytechnique Hauts-de-France (UPHF) a déployé une infrastructure VPN sophistiquée intégrant eduVPN et Checkpoint VPN, conçue pour répondre aux exigences de sécurité élevées d'un établissement accueillant 13 000 utilisateurs. Ce dispositif combine authentification multifacteur (MFA), chiffrement de pointe et intégration aux systèmes d'identité fédérée, tout en s'appuyant sur des protocoles open-source éprouvés comme OpenVPN et IPSec.

## Architecture Technique du VPN UPHF

### Composants Principaux

L'infrastructure VPN s'articule autour de trois éléments clés :

1. **eduVPN** : Solution open-source basée sur OpenVPN 2.x et WireGuard, permettant l'accès sécurisé aux ressources internes via des tunnels chiffrés.
2. **Checkpoint VPN** : Solution propriétaire pour l'accès spécifique aux applications métiers comme la base de données VT, utilisant le protocole propriétaire SSL Network Extender.
3. **ESUP-OTP** : Module d'authentification multifacteur intégré au CAS (Central Authentication Service) de l'université, générant des codes TOTP ou des notifications push.

Le système exploite une architecture redondante avec :

- Un **portail web** (vpn.uphf.fr) pour la gestion des configurations et des appareils autorisés
- Des **serveurs nodes** répartis sur les campus de Valenciennes, Cambrai et Maubeuge assurant le traitement des connexions
- Une intégration au **système d'identité fédérée** via Shibboleth pour l'authentification unique.


### Protocoles et Chiffrement

Les connexions VPN utilisent simultanément :

- **OpenVPN** en UDP/1194 avec chiffrement AES-256-GCM et certificats X.509
- **IPSec/IKEv2** pour la mobilité sur appareils iOS/Android
- **WireGuard** en mode expérimental depuis 2024 pour les débits élevés (recherche collaborative avec l'INSA).

Le trafic est encapsulé selon la norme RFC 3948 pour le NAT-Traversal, garantissant la compatibilité avec les box ADSL grand public. Une étude interne cite un débit moyen de 85 Mbps en UDP et 45 Mbps en TCP sur lien fibre 1 Gbps.

## Mécanismes d'Authentification

### Workflow d'Accès

1. **Phase d'Identification** :
    - Utilisation des identifiants ENT via CAS
    - Vérification des groupes LDAP (personnels/étudiants/contractuels).
2. **Authentification Multifacteur** :
    - Intégration obligatoire d'ESUP-OTP pour les accès distants
    - Choix entre notification push (via app Esup Auth) ou code TOTP 6 chiffres.
3. **Provisioning Dynamique** :
    - Génération de certificats client X.509 à validité limitée (30 jours)
    - Mise à jour automatique via l'API OAuth 2.0 du portail.

### Politiques de Sécurité

- **Durcissement des Sessions** :
    - Verrouillage après 3 échecs d'authentification
    - Session idle timeout de 15 minutes
    - Journalisation centralisée dans Graylog.
- **Contrôle des Appareils** :
    - Whitelisting MAC address pour les postes fixes
    - Profilage des appareils mobiles via Mobile Device Management.


## Configuration Client Multi-Plateforme

### Procédures d'Installation

**Pour eduVPN** :

- **Windows** : Package MSI auto-signé avec préconfiguration des routes spécifiques (193.50.192.0/24)
- **macOS** : Utilisation de Tunnelblick avec profil .ovpn généré dynamiquement.
- **Linux** : Scripts Ansible pour déploiement massif dans les laboratoires de recherche.

**Pour Checkpoint VPN** :

- Client SSL Network Extender (SNX) version 800007075
- Configuration via fichier .snxrc dans le home directory utilisateur.


### Paramètres Avancés

- **Fichiers PAC** :
    - proxy.pac spécifique par campus (Valenciennes/Cambrai/Maubeuge)
    - Détection automatique des ressources internes vs trafic Internet.
- **Optimisation Performances** :
    - MTU ajusté dynamiquement entre 1300-1400 bytes
    - Compression LZO désactivée pour contrer les attaques VORACLE.


## Supervision et Maintenance

### Monitoring en Temps Réel

- Tableaux de bord Grafana avec métriques :
    - Nombre de sessions simultanées (cap à 1500 utilisateurs)
    - Bande passante consommée par protocole
    - Latence moyenne des tunnels.
- Système d'alertes proactives via :
    - SMS Alert pour les incidents majeurs
    - Rocket.Chat pour le support technique.


### Politique de Mises à Jour

- Cycle de patch mensuel aligné sur les advisories RENATER
- Tests de pénétration biannuels via partenariat avec Orange Cyberdefense
- Bascules automatiques vers le datacenter secondaire en cas d'incident.


## Cas d'Usage et Restrictions

### Accès Autorisés

1. **Ressources Pédagogiques** :
    - Moodle
    - Bibliothèque numérique
    - Labos virtuels (VMWare Horizon).
2. **Systèmes Administratifs** :
    - SIGA (gestion scolaire)
    - GPEC (ressources humaines)
    - Base de données recherche HAL-UPHF.

### Restrictions d'Usage

- Interdiction du P2P et du streaming HD
- Filtrage DNS contre les C\&C malware
- Quotas de bande passante (5 Go/jour pour étudiants).


## Intégration avec l'Écosystème de Sécurité

### Interaction avec les Autres Systèmes

- **Authentification Unifiée** : Interfaçage avec Sésame pour la gestion centralisée des identités.
- **Protection Endpoint** : Intégration à WithSecure Elements pour le scan pré-connexion.
- **Gestion de Crise** : Couplage avec SMS Alert pour la coupure d'urgence des tunnels.


### Conformité Réglementaire

- Respect du RGPD via chiffrement AES des logs
- Archivage des métadonnées de connexion pendant 1 an (CNIL DC-004)
- Audit annuel par l'ANSSI dans le cadre du plan Vigipirate.


## Conclusion

Le VPN de l'UPHF illustre une implémentation mature des bonnes pratiques de sécurité Zero Trust, combinant :

- Une **architecture résiliente** avec basculement automatique
- Des **mécanismes d'authentification robustes** (MFA + provisioning dynamique)
- Une **supervision granulaire** permettant une réaction rapide aux incidents

Ce dispositif s'intègre parfaitement dans la stratégie globale de "défense en profondeur" de l'université, complétant les systèmes de détection d'intrusion (IDS) et la politique de durcissement des postes clients. Les investissements continus (650 k€ sur 2023-2025) garantissent son adaptation face à l'évolution des cybermenaces, tout en maintenant une accessibilité optimale pour la communauté universitaire.
