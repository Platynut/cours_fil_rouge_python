from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DOSSIER_PROJET = Path(__file__).resolve().parents[1]
DOSSIER_RENDU = Path(__file__).resolve().parent
CHEMIN_CSV = DOSSIER_PROJET / "observation-meteo-france.csv"
PROPORTION_TEST = 0.2
NOMBRE_MINIMUM_LIGNES = 10
COLONNE_DATE = "Date"
COLONNE_CIBLE = "Température (°C)"
COLONNE_PRECIPITATIONS = "Précipitations dans les 3 dernières heures"
VARIABLES_MODELE = ["Mois", "Heure"]
VARIABLES_VARIANTE = [
    "Mois sin",
    "Mois cos",
    "Heure sin",
    "Heure cos",
]


def chargerDonnees(chemin: Path = CHEMIN_CSV) -> pd.DataFrame:
    """Charge le CSV météo et vérifie qu'il contient les colonnes nécessaires."""
    if not chemin.is_file():
        raise FileNotFoundError(f"Fichier de données introuvable : {chemin}")

    df = pd.read_csv(chemin, sep=";", na_values=["mq"], low_memory=False)
    if df.empty:
        raise ValueError(f"Le fichier de données est vide : {chemin}")

    colonnes_requises = [COLONNE_DATE, COLONNE_CIBLE]
    colonnes_absentes = [colonne for colonne in colonnes_requises if colonne not in df.columns]
    if colonnes_absentes:
        raise ValueError(f"Colonnes absentes du fichier : {colonnes_absentes}")
    return df


def nettoyageDesColonnes(df: pd.DataFrame) -> pd.DataFrame:
    """Conserve les colonnes météo utiles aux graphiques et à la modélisation."""
    colonnes_utiles = [
        COLONNE_DATE,
        COLONNE_CIBLE,
        "Température",
        "Humidité",
        "Pression station",
        "Vitesse du vent moyen 10 mn",
        COLONNE_PRECIPITATIONS,
    ]
    colonnes_presentes = [colonne for colonne in colonnes_utiles if colonne in df.columns]
    colonnes_absentes = [colonne for colonne in colonnes_utiles[:2] if colonne not in df.columns]
    if colonnes_absentes:
        raise ValueError(f"Colonnes nécessaires absentes : {colonnes_absentes}")
    return df[colonnes_presentes].copy()


def gestionValeursManquantes(df: pd.DataFrame) -> pd.DataFrame:
    """Convertit date et cible, puis retire les lignes sans date ou température."""
    df = df.copy()
    df[COLONNE_DATE] = pd.to_datetime(df[COLONNE_DATE], errors="coerce", utc=True)
    df[COLONNE_CIBLE] = pd.to_numeric(df[COLONNE_CIBLE], errors="coerce")

    nombre_initial = len(df)
    df = df.dropna(subset=[COLONNE_DATE, COLONNE_CIBLE]).copy()
    nombre_supprime = nombre_initial - len(df)
    print(
        f"Lignes supprimées car date ou température manquante/invalide : "
        f"{nombre_supprime} sur {nombre_initial} ({nombre_supprime / nombre_initial:.2%})"
    )
    if df.empty:
        raise ValueError("Aucune observation exploitable après le traitement des valeurs manquantes.")
    return df.sort_values(COLONNE_DATE).reset_index(drop=True)


def extractionDeLaDate(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute le mois, l'heure et leur représentation cyclique."""
    df = df.copy()
    df["Mois"] = df[COLONNE_DATE].dt.month.astype(float)
    df["Heure"] = df[COLONNE_DATE].dt.hour.astype(float)
    df["Mois sin"] = np.sin(2 * np.pi * (df["Mois"] - 1) / 12)
    df["Mois cos"] = np.cos(2 * np.pi * (df["Mois"] - 1) / 12)
    df["Heure sin"] = np.sin(2 * np.pi * df["Heure"] / 24)
    df["Heure cos"] = np.cos(2 * np.pi * df["Heure"] / 24)
    df["Année-mois"] = df[COLONNE_DATE].dt.strftime("%Y-%m")
    return df


def calculerMoyenneTemperatureParMois(df: pd.DataFrame) -> pd.DataFrame:
    """Calcule les moyennes, minima et maxima de température par année-mois."""
    aggregation = (
        df.groupby("Année-mois")
        .agg(
            moyenne=(COLONNE_CIBLE, "mean"),
            minimum=(COLONNE_CIBLE, "min"),
            maximum=(COLONNE_CIBLE, "max"),
        )
        .round(1)
    )
    print("Période couverte :", df[COLONNE_DATE].min(), "à", df[COLONNE_DATE].max())
    print(aggregation)
    return aggregation


def preparerDonnees(
    df: pd.DataFrame, noms_colonnes: list[str], nom_cible: str
) -> tuple[pd.DataFrame, pd.Series]:
    """Construit X et y numériques, supprime leurs valeurs manquantes et vérifie les entrées."""
    colonnes_demandees = list(dict.fromkeys([*noms_colonnes, nom_cible]))
    colonnes_absentes = [colonne for colonne in colonnes_demandees if colonne not in df.columns]
    if colonnes_absentes:
        raise ValueError(f"Colonnes demandées absentes : {colonnes_absentes}")
    if not noms_colonnes:
        raise ValueError("Il faut demander au moins une variable explicative.")

    donnees = df[colonnes_demandees].copy()
    for colonne in colonnes_demandees:
        donnees[colonne] = pd.to_numeric(donnees[colonne], errors="coerce")
    nombre_initial = len(donnees)
    donnees = donnees.dropna(subset=colonnes_demandees)
    nombre_supprime = nombre_initial - len(donnees)
    print(
        f"Préparation de {noms_colonnes} : {nombre_supprime} ligne(s) supprimée(s) "
        f"sur {nombre_initial}."
    )

    if len(donnees) < NOMBRE_MINIMUM_LIGNES:
        raise ValueError(
            f"Pas assez de lignes exploitables : {len(donnees)} "
            f"(minimum demandé : {NOMBRE_MINIMUM_LIGNES})."
        )

    X = donnees[noms_colonnes].astype(float)
    y = donnees[nom_cible].astype(float)
    if len(X) != len(y) or not X.index.equals(y.index):
        raise ValueError("X et y ne sont pas alignés.")
    print(f"Dimensions de X : {X.shape} ; dimensions de y : {y.shape}")
    return X, y


def separerEntrainementTest(
    X: pd.DataFrame, y: pd.Series, proportion_test: float = PROPORTION_TEST
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Sépare chronologiquement les observations anciennes et les plus récentes."""
    if not 0 < proportion_test < 1:
        raise ValueError("La proportion de test doit être comprise entre 0 et 1.")
    if len(X) != len(y) or not X.index.equals(y.index):
        raise ValueError("X et y doivent avoir le même nombre de lignes et le même index.")
    if len(X) < NOMBRE_MINIMUM_LIGNES:
        raise ValueError("Nombre de lignes insuffisant pour créer les jeux d'entraînement et de test.")

    indice_coupure = int(len(X) * (1 - proportion_test))
    if indice_coupure < 2 or len(X) - indice_coupure < 1:
        raise ValueError("Le découpage ne laisse pas assez d'observations dans chaque jeu.")
    X_train, X_test = X.iloc[:indice_coupure], X.iloc[indice_coupure:]
    y_train, y_test = y.iloc[:indice_coupure], y.iloc[indice_coupure:]
    print(f"Lignes entraînement : {len(X_train)} ; test : {len(X_test)}")
    return X_train, X_test, y_train, y_test


def entrainerRegressionLineaire(
    X_train: pd.DataFrame, y_train: pd.Series
) -> tuple[float, np.ndarray]:
    """Ajuste une régression linéaire par moindres carrés sur les seules données d'entraînement."""
    if len(X_train) != len(y_train) or len(X_train) == 0:
        raise ValueError("Les données d'entraînement doivent être non vides et alignées.")
    matrice = np.column_stack([np.ones(len(X_train)), X_train.to_numpy(dtype=float)])
    coefficients, _, _, _ = np.linalg.lstsq(matrice, y_train.to_numpy(dtype=float), rcond=None)
    return float(coefficients[0]), coefficients[1:]


def predire(X: pd.DataFrame, constante: float, coefficients: np.ndarray) -> np.ndarray:
    """Calcule les prédictions à partir de la constante et des coefficients ajustés."""
    if X.shape[1] != len(coefficients):
        raise ValueError("Le nombre de colonnes de X ne correspond pas aux coefficients.")
    return constante + X.to_numpy(dtype=float) @ coefficients


def calculerMetriques(valeurs_reelles: pd.Series, predictions: np.ndarray) -> dict[str, float]:
    """Calcule MAE, RMSE et R², avec les erreurs exprimées en degrés Celsius."""
    reelles = valeurs_reelles.to_numpy(dtype=float)
    if len(reelles) != len(predictions) or len(reelles) == 0:
        raise ValueError("Les valeurs réelles et les prédictions doivent être non vides et alignées.")
    erreurs = reelles - predictions
    variance_totale = np.sum((reelles - np.mean(reelles)) ** 2)
    r2 = 1 - np.sum(erreurs**2) / variance_totale if variance_totale > 0 else float("nan")
    return {
        "MAE": float(np.mean(np.abs(erreurs))),
        "RMSE": float(np.sqrt(np.mean(erreurs**2))),
        "R²": float(r2),
    }


def afficherEvaluation(
    nom_modele: str,
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
) -> tuple[np.ndarray, dict[str, float], dict[str, float]]:
    """Entraîne, affiche les coefficients et compare les scores train/test et au modèle naïf."""
    constante, coefficients = entrainerRegressionLineaire(X_train, y_train)
    predictions_train = predire(X_train, constante, coefficients)
    predictions_test = predire(X_test, constante, coefficients)
    metriques_train = calculerMetriques(y_train, predictions_train)
    metriques_test = calculerMetriques(y_test, predictions_test)

    print(f"\n{nom_modele}")
    print(f"Constante : {constante:.3f} °C")
    for nom, coefficient in zip(X_train.columns, coefficients):
        print(f"Coefficient {nom} : {coefficient:.3f}")
    print("Métriques entraînement :", metriques_train)
    print("Métriques test :", metriques_test)

    prediction_naive = np.full(len(y_test), y_train.mean())
    print("Référence naïve (moyenne du train), test :", calculerMetriques(y_test, prediction_naive))
    return predictions_test, metriques_train, metriques_test


def enregistrerGraphiques(df: pd.DataFrame) -> None:
    """Enregistre les graphiques d'exploration et la figure des erreurs du modèle principal."""
    DOSSIER_RENDU.mkdir(parents=True, exist_ok=True)

    moyennes_mensuelles = (
        df.set_index(COLONNE_DATE)[COLONNE_CIBLE].resample("MS").mean()
    )
    figure, axes = plt.subplots(2, 1, figsize=(12, 8))
    axes[0].plot(df[COLONNE_DATE], df[COLONNE_CIBLE], linewidth=0.6)
    axes[0].set_title("Température à chaque observation")
    axes[0].set_ylabel("Température (°C)")
    axes[0].grid(True)
    axes[1].plot(moyennes_mensuelles.index, moyennes_mensuelles)
    axes[1].set_title("Température moyenne mensuelle")
    axes[1].set_xlabel("Date")
    axes[1].set_ylabel("Température moyenne (°C)")
    axes[1].grid(True)
    figure.tight_layout()
    figure.savefig(DOSSIER_RENDU / "evolution_temperature.png")
    plt.close(figure)

    if COLONNE_PRECIPITATIONS in df.columns:
        precipitations = pd.to_numeric(df[COLONNE_PRECIPITATIONS], errors="coerce").dropna()
        donnees_pluie = df[[COLONNE_DATE]].copy()
        donnees_pluie[COLONNE_PRECIPITATIONS] = pd.to_numeric(
            df[COLONNE_PRECIPITATIONS], errors="coerce"
        )
        donnees_pluie = donnees_pluie.dropna(subset=[COLONNE_PRECIPITATIONS])
        pluies_mensuelles = (
            donnees_pluie.set_index(COLONNE_DATE)[COLONNE_PRECIPITATIONS]
            .resample("MS")
            .sum(min_count=1)
        )
        figure, axe = plt.subplots(figsize=(12, 5))
        axe.bar(pluies_mensuelles.index, pluies_mensuelles, width=20)
        axe.set_title("Cumul mensuel des précipitations dans les 3 dernières heures")
        axe.set_xlabel("Date")
        axe.set_ylabel("Précipitations cumulées (mm)")
        axe.grid(axis="y")
        figure.tight_layout()
        figure.savefig(DOSSIER_RENDU / "precipitations.png")
        plt.close(figure)

        valeurs_positives = precipitations[precipitations > 0]
        if not valeurs_positives.empty:
            figure, axe = plt.subplots(figsize=(8, 5))
            axe.hist(valeurs_positives, bins=30)
            axe.set_title("Distribution des précipitations non nulles (3 heures)")
            axe.set_xlabel("Précipitations (mm)")
            axe.set_ylabel("Nombre d'observations")
            axe.grid(axis="y")
            figure.tight_layout()
            figure.savefig(DOSSIER_RENDU / "distribution_precipitations.png")
            plt.close(figure)

    colonnes_relation = [
        colonne
        for colonne in ["Humidité", "Pression station", "Vitesse du vent moyen 10 mn"]
        if colonne in df.columns
    ]
    if colonnes_relation:
        figure, axes = plt.subplots(
            1, len(colonnes_relation), figsize=(5 * len(colonnes_relation), 4)
        )
        axes = np.atleast_1d(axes)
        for axe, colonne in zip(axes, colonnes_relation):
            valeurs = pd.to_numeric(df[colonne], errors="coerce")
            axe.scatter(valeurs, df[COLONNE_CIBLE], s=8, alpha=0.25)
            axe.set_xlabel(colonne)
            axe.set_ylabel("Température (°C)")
            axe.grid(True)
        figure.suptitle("Relations entre température et variables météo")
        figure.tight_layout()
        figure.savefig(DOSSIER_RENDU / "relations_variables.png")
        plt.close(figure)


def enregistrerGraphiqueRegression(
    y_test: pd.Series, predictions: np.ndarray, dates_test: pd.Series
) -> None:
    """Enregistre les prédictions et les erreurs en fonction de la date du jeu de test."""
    erreurs = y_test.to_numpy(dtype=float) - predictions
    figure, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    axes[0].plot(dates_test, y_test.to_numpy(), label="Valeurs réelles", linewidth=0.8)
    axes[0].plot(dates_test, predictions, label="Prédictions", linewidth=0.8)
    axes[0].set_ylabel("Température (°C)")
    axes[0].set_title("Températures réelles et prédites — jeu de test")
    axes[0].legend()
    axes[0].grid(True)
    axes[1].scatter(dates_test, erreurs, s=8, alpha=0.5)
    axes[1].axhline(0, color="black", linewidth=1)
    axes[1].set_ylabel("Erreur (°C)")
    axes[1].set_xlabel("Date")
    axes[1].set_title("Erreur = valeur réelle − prédiction")
    axes[1].grid(True)
    figure.tight_layout()
    figure.savefig(DOSSIER_RENDU / "regression_erreurs.png")
    plt.close(figure)


def main() -> pd.DataFrame:
    """Exécute le chargement, le nettoyage, l'exploration et l'évaluation des modèles."""
    donnees_brutes = chargerDonnees()
    donnees = nettoyageDesColonnes(donnees_brutes)
    donnees = gestionValeursManquantes(donnees)
    donnees = extractionDeLaDate(donnees)
    calculerMoyenneTemperatureParMois(donnees)
    enregistrerGraphiques(donnees)

    X, y = preparerDonnees(donnees, VARIABLES_MODELE, COLONNE_CIBLE)
    X_train, X_test, y_train, y_test = separerEntrainementTest(X, y)
    print(
        "Période entraînement :",
        donnees.loc[y_train.index, COLONNE_DATE].min(),
        "à",
        donnees.loc[y_train.index, COLONNE_DATE].max(),
    )
    print(
        "Période test :",
        donnees.loc[y_test.index, COLONNE_DATE].min(),
        "à",
        donnees.loc[y_test.index, COLONNE_DATE].max(),
    )
    dates_test = donnees.loc[y_test.index, COLONNE_DATE]
    predictions, _, _ = afficherEvaluation(
        "Modèle principal : mois et heure",
        X_train,
        X_test,
        y_train,
        y_test,
    )
    enregistrerGraphiqueRegression(y_test, predictions, dates_test)

    X_variante, y_variante = preparerDonnees(donnees, VARIABLES_VARIANTE, COLONNE_CIBLE)
    X_train_v, X_test_v, y_train_v, y_test_v = separerEntrainementTest(
        X_variante, y_variante
    )
    afficherEvaluation(
        "Variante : représentation cyclique du mois et de l'heure",
        X_train_v,
        X_test_v,
        y_train_v,
        y_test_v,
    )
    return donnees


if __name__ == "__main__":
    main()
