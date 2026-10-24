import pandas as pd
import projet_meteo as pm
import matplotlib.pyplot as plt
from pathlib import Path



def grapheTemperaturesCelsius(df: pd.DataFrame) -> None:
    # Permet de créer deux graphes des températures en Celsius
    # param:
    #     df: DataFrame à analyser
    # return: None
    df = df[["Date", "Température (°C)"]].copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df["Température (°C)"] = pd.to_numeric(df["Température (°C)"])

    print("Températures manquantes :", df["Température (°C)"].isna().sum())
    df = df.dropna(subset=["Date"]).sort_values("Date")
    moyennes_mensuelles = (df.set_index("Date")["Température (°C)"].resample("MS").mean())

    # Le premier graphique montre chaque observation, le second les moyennes mensuelles.
    fig, axes = plt.subplots(2, 1, figsize=(12, 8))

    axes[0].plot(df["Date"], df["Température (°C)"])
    axes[0].set_title("Température à chaque observation")
    axes[0].set_ylabel("Température (°C)")
    axes[0].grid(True)

    axes[1].plot(moyennes_mensuelles.index, moyennes_mensuelles)
    axes[1].set_title("Température moyenne mensuelle")
    axes[1].set_xlabel("Date")
    axes[1].set_ylabel("Température moyenne (°C)")
    axes[1].grid(True)

    # On enregistre l'image
    fig.tight_layout()
    fig.savefig("evolution_temperature.png")



def graphePrecipitations(df: pd.DataFrame) -> None:
    colonne = "Précipitations dans les 3 dernières heures"
    df = df[["Date", colonne]].copy()

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df[colonne] = pd.to_numeric(df[colonne], errors="coerce")

    valeurs = df[colonne].dropna()
    print(f"Minimum : {valeurs.min()}")
    print(f"Maximum : {valeurs.max()}")
    print(f"Proportion de zéros : {(valeurs == 0).mean():.1%}")
    print(f"Valeurs négatives : {(valeurs < 0).sum()}")

    cumuls_mensuels = (
        df.dropna(subset=["Date"])
        .set_index("Date")[colonne]
        .resample("MS")
        .sum(min_count=1)
    )

    plt.figure(figsize=(10, 5))
    plt.bar(cumuls_mensuels.index.strftime("%Y-%m"), cumuls_mensuels)
    plt.tick_params(axis="x", labelbottom=False)
    plt.title("Cumul mensuel des précipitations")
    plt.xlabel("Mois")
    plt.ylabel("Précipitations cumulées (mm)")

    plt.tight_layout()
    plt.savefig("precipitations.png")

if __name__ == "__main__":
    df = pm.nettoyageDesColonnes(pm.df)
    df = pm.gestionValeursManquantes(df)
    grapheTemperaturesCelsius(df)
    graphePrecipitations(pm.df)