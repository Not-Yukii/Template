# Évaluation Complète des Dispositifs de Sécurité à l'Université Polytechnique Hauts-de-France (UPHF)

L'Université Polytechnique Hauts-de-France (UPHF) a mis en place un dispositif de sécurité multicouche qui couvre l'ensemble des aspects de la protection informatique, physique et organisationnelle. Cette évaluation détaillée examine les dix volets principaux de la stratégie de sécurité de l'établissement, s'appuyant sur une approche de "défense en profondeur" qui garantit la protection du système d'information, la sécurisation des réseaux et la sûreté des usagers sur les cinq campus. Les mesures mises en place répondent aux exigences nationales de l'ANSSI et de RENATER, tout en s'adaptant aux spécificités d'un établissement d'enseignement supérieur accueillant plus de 13 000 étudiants et personnels.

## Gouvernance et Politique de Sécurité des Systèmes d'Information

### Structure Organisationnelle de la SSI

La Direction du Numérique (DNum) pilote la Sécurité des Systèmes d'Information sous l'autorité d'une chaîne fonctionnelle bien définie. Cette organisation respecte la directive interministérielle n°901 et comprend un Haut Fonctionnaire de Défense et de Sécurité (HFDS), un Fonctionnaire de Sécurité de Défense (FSD) et un Responsable de la Sécurité des Systèmes d'Information (RSSI). Le chef d'établissement, en tant qu'Autorité Qualifiée pour la SSI (AQSSI), définit la politique de sécurité des systèmes d'information adaptée à l'université et veille à la mise en œuvre des dispositions réglementaires.

La politique de sécurité s'appuie sur une Politique de Sécurité de l'État (PSSIE) adaptée aux spécificités universitaires. Cette politique vise à garantir quatre objectifs fondamentaux : la confidentialité, l'intégrité, la disponibilité et la traçabilité des données. Un comité de pilotage trimestriel associe la DNum, la direction générale des services, le service juridique et les représentants des laboratoires pour arbitrer le plan d'actions et adapter la stratégie de sécurité aux évolutions technologiques et réglementaires.

### Cadre Réglementaire et Procédures

L'établissement a mis en place un règlement intérieur des usages des systèmes d'information validé en conseil d'administration, définissant les responsabilités, droits et devoirs de chaque usager. Ce cadre juridique s'appuie également sur la réglementation PSSIE qui définit les orientations nationales en matière de sécurité des systèmes d'information auxquelles les établissements publics d'État doivent se soumettre. Un point de contact incident centralisé (rssi@uphf.fr) assure le suivi d'un processus interne d'escalade et de déclaration aux autorités compétentes (ANSSI, CNIL) en cas d'incident majeur.

## Gestion des Identités et Authentification

### Système d'Authentification Multifacteur

L'UPHF a déployé ESUP-OTP, une solution d'authentification multifacteur (MFA) libre intégrée au Système Central d'Authentification (CAS) de l'établissement. Cette solution exige obligatoirement l'authentification multifacteur pour l'accès à la plupart des applications sensibles, ajoutant un deuxième niveau de sécurité à la connexion. Les utilisateurs disposent de deux possibilités pour valider la connexion : un système de notifications push sur smartphone iOS ou Android, ou un code temporel généré automatiquement toutes les 30 secondes.

Le système ESUP-OTP est particulièrement utilisé pour le télétravail et l'accès distant aux ressources critiques. Il s'intègre parfaitement avec le portail eduVPN pour sécuriser les connexions externes. La solution offre une interface de gestion accessible via mfa.uphf.fr permettant aux utilisateurs de configurer leurs préférences d'authentification.

### Portail de Gestion des Identités

Le portail Sésame constitue l'interface centrale de gestion des identifiants ENT, permettant la réinitialisation autonome des mots de passe avec des exigences de complexité renforcées et une expiration annuelle. Ce système s'appuie sur un provisioning SCIM automatisé entre l'annuaire LDAP, l'Active Directory et les applications SaaS, garantissant la cohérence des identités à travers l'ensemble de l'infrastructure informatique.

### Carte Multi-Services et Contrôle d'Accès

La Carte Multi-Services (CMS) utilise la technologie sans contact MIFARE DESFire EV2 et constitue le badge individuel permettant l'accès aux bâtiments, salles spécialisées et parkings. Cette carte intègre également les services IZLY/CROUS et de la bibliothèque universitaire, centralisant l'ensemble des accès et services sur un support unique sécurisé. Le système de lecture de badges couvre 100% des accès sensibles avec un verrouillage automatique hors horaires d'ouverture.

## Architecture Réseau et Cybersécurité

### Infrastructure Réseau Sécurisée

L'infrastructure réseau de l'UPHF s'appuie sur un backbone redondant 10 Gb/s entre les datacentres Mont Houy et Tertiales utilisant de la fibre noire. La commutation cœur repose sur des équipements Cisco Nexus avec un routage BGP vers RENATER, garantissant une connectivité haute performance et sécurisée. Le réseau utilise une segmentation VLAN d'isolation comprenant les environnements de production, DMZ, recherche, visioconférence et IoT building, avec un filtrage "east-west" via des pare-feux internes.

Le contrôle d'accès réseau (NAC) 802.1X est déployé sur le campus câblé avec une authentification dot1x et une assignation dynamique de VLAN. Ce système permet la mise en quarantaine automatique des postes non conformes, renforçant la sécurité périmétrique du réseau filaire. La supervision centralisée s'effectue via Centreon et Grafana, avec des alertes envoyées via SMS Alert et Rocket.Chat.

### Réseau Sans Fil Sécurisé

L'UPHF dispose de plus de 400 points d'accès WiFi répartis sur les cinq campus (Mont Houy, Tertiales, Arenberg, Cambrai et Maubeuge). Ces points d'accès sont gérés par des contrôleurs Cisco 9800-L et proposent une segmentation via deux SSID distincts : "eduroam" pour l'accès Internet des visiteurs et étudiants, et "personnel" pour l'accès à l'intranet.

L'authentification utilise les protocoles 802.1X EAP-TTLS ou PEAP avec des certificats Digicert/TERENA, et un chiffrement WPA2 Entreprise/AES. L'outil CAT (Configuration Assistant Tool) permet la configuration automatique des postes, facilitant la connexion sécurisée pour les utilisateurs. Sur le réseau "personnel", un script proxy.pac est obligatoire pour filtrer le trafic sortant et journaliser l'activité réseau.

### Protection des Postes de Travail

La protection endpoint s'appuie sur la solution WithSecure Elements (anciennement F-Secure) déployée sur 100% des postes raccordés au réseau. Cette solution EDR (Endpoint Detection \& Response) est gérée centralement par la DNum et inclut l'antivirus, la protection en temps réel, DeepGuard, DataGuard et le contrôle des applications. Le patch management utilise WSUS et Ansible pour les environnements Windows et Linux, avec un délai maximum de 15 jours après publication des CVE critiques.

## Accès Distants et Connectivité Sécurisée

### Solution VPN eduVPN

Le service eduVPN propose un tunnel VPN utilisant les protocoles IPSec et OpenVPN pour accéder de l'extérieur aux ressources internes comme les serveurs et bases de données. Ce service est réservé aux personnels manipulant des données sensibles et nécessite une authentification CAS couplée à ESUP-OTP pour renforcer la sécurité. L'accès VPN constitue un élément essentiel de la stratégie de télétravail sécurisé de l'établissement.

### Bastion SSH et Reverse Proxy

L'accès aux serveurs de recherche s'effectue via un bastion SSH utilisant la solution Teleport, avec une centralisation des logs sur Graylog. Cette architecture garantit la traçabilité et le contrôle des accès administratifs aux systèmes critiques. Un reverse proxy Nginx avec authentification SAML sécurise l'accès aux applications web on-premise, maintenant une authentification unique pour l'ensemble des services.

### Filtrage et Surveillance du Trafic

Un proxy PAC par campus filtre le trafic sortant et journalise l'activité réseau. Cette solution permet un contrôle granulaire des accès Internet tout en conservant les logs nécessaires pour les investigations en cas d'incident. La supervision s'effectue par des contrôleurs Cisco et des sondes de détection d'anomalies, permettant une détection proactive des menaces.

## Sûreté Physique et Vidéoprotection

### Services de Gardiennage 24h/24

L'UPHF bénéficie de contrats de gardiennage externe assurant une surveillance permanente 24h/24. Ces prestations couvrent les patrouilles de sécurité, l'ouverture et fermeture des bâtiments, ainsi que la gestion des alarmes. Le contrat de gardiennage 2025-2029, identifié sous l'avis de marché 226489-2025, assure la continuité de ce service essentiel pour la sécurité physique des campus.

Les équipes de sécurité travaillent depuis un poste central de sécurité et maintiennent une liaison constante avec les forces de l'ordre locales. Une convention spécifique avec la Gendarmerie et le SDIS garantit une intervention en moins de 10 minutes sur le campus Mont Houy. Cette réactivité constitue un élément clé du dispositif de sûreté de l'établissement.

### Système de Vidéoprotection

Le système de vidéoprotection a été autorisé par arrêté préfectoral en 2018 et fait l'objet d'un budget de 650k€ pour la maintenance et l'amélioration. Les caméras IP utilisées offrent un stockage chiffré des enregistrements, conservés pendant 30 jours conformément à la réglementation. La consultation des enregistrements est limitée aux agents assermentés, garantissant le respect de la vie privée et des procédures légales.

Le déploiement de la vidéoprotection s'inscrit dans une démarche progressive d'amélioration de la sûreté, particulièrement sur les zones sensibles et les accès principaux des bâtiments. Le système contribue à la fois à la prévention des incidents et à l'investigation post-incident en cas de problème de sécurité.

## Mesures Vigipirate et Gestion de Crise

### Plan Vigipirate Renforcé

L'UPHF applique rigoureusement le plan Vigipirate avec un affichage obligatoire des consignes, un contrôle visuel des sacs et une limitation d'accès hors heures. Une cellule de crise et un Groupe Vigipirate réunissent la direction, la sécurité et la gendarmerie référente pour coordonner les mesures de sûreté. Ces dispositifs permettent une adaptation rapide du niveau de sécurité en fonction de la menace terroriste nationale.

Le plan inclut des procédures de verrouillage rapide des bâtiments et une restriction des accès secondaires en cas d'élévation du niveau d'alerte. Les équipes de sécurité sont formées à l'application de ces mesures exceptionnelles tout en maintenant la continuité des activités pédagogiques et de recherche.

### Système d'Alerte SMS Alert

Le service "SMS Alert" permet la diffusion d'alertes multi-canaux (SMS, email, Rocket.Chat) aux étudiants et personnels inscrits en cas d'événements majeurs comme des attentats ou intempéries. Ce système, intégré à la série "La Minute Numérique", garantit une communication rapide et efficace vers l'ensemble de la communauté universitaire en situation de crise.

### Continuité d'Activité et Plans de Secours

Les plans de continuité d'activité (PCA) et de reprise d'activité (PRA) s'appuient sur la réplication des machines virtuelles via Veeam vers un datacentre secondaire. Des tests de bascule semestriels valident l'efficacité de ces dispositifs de sauvegarde. Des sauvegardes hors site et la réplication des données critiques complètent ce dispositif de continuité.

Les procédures d'évacuation incendie font l'objet d'exercices annuels, et l'établissement dispose de défibrillateurs sur chaque site ainsi que d'équipes d'intervention SSIAP niveau . Cette approche globale de la gestion de crise couvre tant les aspects informatiques que la sécurité des personnes.

## Sensibilisation et Formation à la Cybersécurité

### Programme "La Minute Numérique"

L'UPHF a développé un programme de sensibilisation innovant avec la série vidéo "La Minute Numérique" diffusée chaque semaine. Cette série traite des sujets essentiels comme le phishing, l'authentification multifacteur, le service SMS Alert et les bonnes pratiques de sécurité informatique. L'épisode \#11 est spécifiquement dédié au service SMS Alert, démontrant l'importance accordée à la communication de crise.

Ce format court et accessible permet une diffusion large des messages de sécurité auprès de l'ensemble de la communauté universitaire. Les vidéos constituent un support pédagogique efficace pour sensibiliser aux risques cyber et promouvoir l'adoption des bonnes pratiques.

### Formation MOOC et Ressources Internes

Un MOOC interne sur Moodle traite spécifiquement du RGPD, des bonnes pratiques de mots de passe et de la gestion des incidents. Cette formation en ligne permet à chaque membre de la communauté universitaire d'acquérir les connaissances de base en cybersécurité. La charte RENATER est signée par tous les usagers lors de la première connexion ENT, formalisant l'engagement de chacun dans la sécurité collective.

### Campagnes de Phishing et Évaluation

Des campagnes de phishing trimestrielles utilisant la plateforme "Ocean Learning Platform" permettent d'évaluer et d'améliorer la vigilance des utilisateurs. Ces exercices pratiques constituent un complément essentiel à la formation théorique et permettent d'identifier les besoins de sensibilisation spécifiques.

## Protection des Communications et Messagerie

### Sécurisation de la Messagerie

La protection de la messagerie s'appuie sur un système de sandboxing email utilisant Proofpoint. Les protocoles SPF, DKIM et DMARC sont enforced pour lutter contre l'usurpation d'identité et le phishing. Cette approche multicouche garantit une protection efficace contre les menaces véhiculées par email, vecteur privilégié des cyberattaques.

L'authentification multifacteur ESUP-OTP est particulièrement déployée pour les connexions extérieures à la messagerie Zimbra, ajoutant une couche de sécurité supplémentaire pour l'accès distant. Cette mesure protège les comptes de messagerie contre les tentatives d'intrusion, même en cas de compromission des mots de passe.

### Conformité RGPD et Protection des Données

Un Délégué à la Protection des Données (DPO) assure la conformité RGPD et traite les demandes d'accès. Cette fonction garantit le respect de la réglementation européenne sur la protection des données personnelles, enjeu crucial pour un établissement d'enseignement supérieur manipulant de nombreuses données sensibles.

## Formation Spécialisée en Cybersécurité

### Master Cyber-Défense et Sécurité de l'Information

L'UPHF propose un Master Cyber-Défense et Sécurité de l'Information (CDSI) co-délivré avec l'INSA Hauts-de-France. Cette formation de niveau BAC+5 sur 120 crédits ECTS forme des professionnels qualifiés aux concepts, méthodes et techniques de traitement de la sécurité et de gestion du risque liés aux systèmes d'information. Le programme couvre la lutte contre la cybercriminalité, les failles des systèmes d'information, la sécurité numérique et le codage de l'information.

Cette formation contribue directement à l'écosystème de cybersécurité régional en formant les futurs professionnels qui renforceront la sécurité des organisations publiques et privées. Les partenariats avec des entreprises comme Athéos/Orange CyberDefense, Dunasys, Cassidian, l'ANSSI et Thales garantissent l'adéquation de la formation aux besoins du marché.

## Conclusion

L'UPHF a mis en place un dispositif de sécurité exemplaire qui couvre l'ensemble des dimensions de la protection d'un établissement d'enseignement supérieur moderne. La stratégie de "défense en profondeur" adoptée garantit une protection multicouche allant de la gouvernance SSI aux mesures de sûreté physique, en passant par la cybersécurité et la sensibilisation des utilisateurs.

La maturité du dispositif se reflète dans l'intégration cohérente des différents composants : authentification multifacteur généralisée, segmentation réseau avancée, protection endpoint centralisée, surveillance continue et gestion de crise structurée. L'établissement démontre également sa capacité d'innovation avec des initiatives comme "La Minute Numérique" et son engagement dans la formation des futurs experts en cybersécurité.

Les investissements consentis (650k€ pour la vidéoprotection, contrats de gardiennage pluriannuels, infrastructure réseau redondante) témoignent de la priorité accordée à la sécurité. Cette approche globale positionne l'UPHF comme un établissement de référence en matière de sécurité universitaire, capable de faire face aux défis croissants de la cybersécurité tout en maintenant l'ouverture nécessaire à sa mission d'enseignement et de recherche.
