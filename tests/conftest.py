"""Les logs de l'appli vont sur la sortie d'erreur pendant les tests, comme
dans le conteneur (``lmelp-pap`` les configure au démarrage)."""

from lmelp_pap import logs


logs.configurer()
