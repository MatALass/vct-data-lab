"""
Dashboard VCT EMEA — Roster Intelligence
==========================================
Lit le fichier Excel produit par le notebook (vlr_emea_stage2_roster_analysis_*.xlsx)
et propose une exploration interactive : qui devrait partir, adéquation de rôle,
recrutement (VCT + vivier Challengers), évolution multi-stage.

Lancement :
    pip install streamlit plotly pandas openpyxl
    streamlit run app.py
"""

import io
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="VCT EMEA — Roster Intelligence", layout="wide", page_icon="🎯")

ROLE_COLORS = {
    "Duelist": "#fa4454",
    "Controller": "#3ba7ff",
    "Initiator": "#2ecc71",
    "Sentinel": "#f39c12",
}

# --------------------------------------------------------------------------
# Chargement des données
# --------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def load_workbook(file_bytes: bytes) -> dict:
    """Charge toutes les feuilles utiles du classeur Excel produit par le notebook.
    Retourne un dict {nom_logique: DataFrame ou None si la feuille est absente}."""
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    sheets = xls.sheet_names

    def read(name):
        return pd.read_excel(xls, sheet_name=name) if name in sheets else None

    return {
        "joueurs": read("Joueurs"),
        "equipes": read("Résumé équipes"),
        "roles_par_equipe": read("Rôles par équipe"),
        "composition_nationale": read("Composition nationale"),
        "synthese_equipes": read("Synthèse équipes"),
        "transferts": read("Spéculations transferts"),
        "trajectoires": read("Trajectoires S1-S2"),
        "bilan_roster": read("Bilan transferts S1-S2"),
        "score_composite": read("Score composite équipes"),
        "historique_3_stages": read("Historique 3 stages"),
        "tendance_equipes": read("Tendance équipes"),
        "pool_vcl": read("Pool Challengers VCL"),
        "adequation_role": read("Adequation role"),
    }


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "roster"


def sidebar_loader():
    st.sidebar.title("🎯 VCT EMEA")
    st.sidebar.caption("Roster Intelligence Dashboard")

    # Propose directement les .xlsx déjà présents dans data/ (généré par le notebook)
    found = sorted(DATA_DIR.glob("*.xlsx")) if DATA_DIR.exists() else []
    file_bytes = None

    if found:
        options = ["— choisir —"] + [f.name for f in found]
        choice = st.sidebar.selectbox(f"Fichier trouvé dans {DATA_DIR.name}/", options)
        if choice != "— choisir —":
            file_bytes = (DATA_DIR / choice).read_bytes()

    uploaded = st.sidebar.file_uploader("...ou dépose un autre fichier Excel", type=["xlsx"])
    if uploaded is not None:
        file_bytes = uploaded.read()

    if file_bytes is None:
        st.sidebar.info(f"Dépose un fichier Excel, ou place-le dans {DATA_DIR}/ pour qu'il apparaisse ici.")
        st.stop()

    return load_workbook(file_bytes)


data = sidebar_loader()
df_joueurs = data["joueurs"]

if df_joueurs is None:
    st.error("La feuille 'Joueurs' est introuvable dans ce fichier — impossible de continuer.")
    st.stop()

# Filtre par défaut : échantillon suffisant (si la colonne existe)
if "sample_ok" in df_joueurs.columns:
    df_valid = df_joueurs[df_joueurs["sample_ok"].fillna(False)].copy()
else:
    df_valid = df_joueurs.copy()

role_col = "role_final" if "role_final" in df_valid.columns else "main_role"

page = st.sidebar.radio(
    "Navigation",
    [
        "Vue d'ensemble",
        "Qui devrait partir ?",
        "Adéquation de rôle",
        "Recrutement (VCT + Challengers)",
        "Évolution multi-stage",
    ],
)

st.sidebar.markdown("---")
st.sidebar.caption(
    "⚠️ Ces vues sont des pistes de lecture statistiques, pas des prédictions. "
    "Contrats, budgets, coaching, et volonté des joueurs ne sont pas dans ces données."
)

# --------------------------------------------------------------------------
# PAGE 1 — Vue d'ensemble
# --------------------------------------------------------------------------
if page == "Vue d'ensemble":
    st.title("Vue d'ensemble des équipes")

    teams = sorted(df_valid["team_full"].dropna().unique())
    team = st.selectbox("Équipe", teams)

    team_df = df_valid[df_valid["team_full"] == team].copy()

    col1, col2, col3 = st.columns(3)
    if data["equipes"] is not None and "match_win_rate" in data["equipes"].columns:
        wr_row = data["equipes"][data["equipes"]["team_full"] == team]
        wr = wr_row["match_win_rate"].values[0] if not wr_row.empty else None
        col1.metric("Taux de victoire (matchs)", f"{wr:.0%}" if wr is not None else "—")
    if "team_slot" in team_df.columns:
        n_flex = (team_df["team_slot"] == "Flex").sum()
        structure = f"{n_flex} joueur(s) flex" if n_flex else "Double Duelist"
        col2.metric("Structure", structure)
    col3.metric("Joueurs (échantillon suffisant)", len(team_df))

    st.subheader("Roster")
    show_cols = [c for c in [
        "player", role_col, "rating", "performance_index_role", "rating_gap_vs_team",
        "is_flex", "is_igl", "nationality",
    ] if c in team_df.columns]
    st.dataframe(
        team_df[show_cols].sort_values("performance_index_role", ascending=False)
        if "performance_index_role" in team_df.columns else team_df[show_cols],
        use_container_width=True, hide_index=True,
    )

    if data["roles_par_equipe"] is not None:
        st.subheader("Répartition des rôles — toutes équipes")
        rc = data["roles_par_equipe"].set_index("team_full")
        fig = px.imshow(
            rc, text_auto=True, color_continuous_scale="YlOrRd", aspect="auto",
            labels=dict(color="Nb de joueurs"),
        )
        st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------------------------------
# PAGE 2 — Qui devrait partir ?
# --------------------------------------------------------------------------
elif page == "Qui devrait partir ?":
    st.title("Qui devrait partir ? (pistes statistiques)")
    st.caption(
        "Classement par indice de performance normalisé par rôle et écart vs la moyenne des "
        "coéquipiers. Un IGL déclaré en bas de classement n'est pas forcément un signal de "
        "faiblesse — voir la colonne dédiée."
    )

    teams = ["Toutes"] + sorted(df_valid["team_full"].dropna().unique())
    team_filter = st.selectbox("Filtrer par équipe", teams)

    plot_df = df_valid if team_filter == "Toutes" else df_valid[df_valid["team_full"] == team_filter]
    plot_df = plot_df.dropna(subset=["performance_index_role"]) if "performance_index_role" in plot_df.columns else plot_df

    sort_col = "performance_index_role" if "performance_index_role" in plot_df.columns else "rating"
    plot_df = plot_df.sort_values(sort_col)

    labels = plot_df["player"] + " (" + plot_df["team_full"].fillna("?") + ")"
    if "is_igl" in plot_df.columns:
        labels = labels + plot_df["is_igl"].map({True: " 🎯", False: ""}).fillna("")

    colors = ["#e74c3c" if v < 0 else "#27ae60" for v in plot_df[sort_col]]

    fig = go.Figure(go.Bar(
        x=plot_df[sort_col], y=labels, orientation="h",
        marker_color=colors,
    ))
    fig.update_layout(
        height=max(400, 20 * len(plot_df)),
        xaxis_title="Indice de performance normalisé par rôle",
        yaxis_title="",
    )
    st.plotly_chart(fig, use_container_width=True)

    show_cols = [c for c in [
        "player", "team_full", role_col, "rating", "performance_index_role",
        "rating_gap_vs_team", "is_igl",
    ] if c in plot_df.columns]
    st.dataframe(plot_df[show_cols], use_container_width=True, hide_index=True)

# --------------------------------------------------------------------------
# PAGE 3 — Adéquation de rôle
# --------------------------------------------------------------------------
elif page == "Adéquation de rôle":
    st.title("Le joueur est-il bien casté dans son rôle ?")
    st.caption(
        "Croise la confiance de rôle (part du rôle dominant dans le pool d'agents joués) et "
        "la performance normalisée dans ce rôle. Quatre quadrants : bien casté, spécialiste "
        "sous-performant, flex qui marche, profil flou à surveiller."
    )

    needed = {"role_confidence", "performance_index_role"}
    if not needed.issubset(df_valid.columns):
        st.warning("Colonnes 'role_confidence' / 'performance_index_role' absentes de ce fichier.")
    else:
        plot_df = df_valid.dropna(subset=["role_confidence", "performance_index_role"]).copy()

        fig = px.scatter(
            plot_df, x="role_confidence", y="performance_index_role",
            color=role_col, color_discrete_map=ROLE_COLORS,
            hover_data=["player", "team_full"],
            labels={"role_confidence": "Confiance de rôle (%)", "performance_index_role": "Performance normalisée"},
        )
        fig.add_hline(y=0, line_dash="dash", line_color="grey")
        fig.add_vline(x=60, line_dash="dash", line_color="grey")
        fig.update_traces(marker=dict(size=11, line=dict(width=1, color="white")))
        fig.update_layout(height=650)
        st.plotly_chart(fig, use_container_width=True)

        if "role_fit" in df_valid.columns:
            st.subheader("Répartition par catégorie")
            st.bar_chart(df_valid["role_fit"].value_counts())
            st.dataframe(
                df_valid[["player", "team_full", role_col, "role_confidence", "performance_index_role", "role_fit"]]
                .sort_values("role_fit"),
                use_container_width=True, hide_index=True,
            )

# --------------------------------------------------------------------------
# PAGE 4 — Recrutement
# --------------------------------------------------------------------------
elif page == "Recrutement (VCT + Challengers)":
    st.title("Quel profil pour compléter ce roster ?")

    teams = sorted(df_valid["team_full"].dropna().unique())
    col1, col2 = st.columns(2)
    team = col1.selectbox("Équipe à renforcer", teams)
    role = col2.selectbox("Rôle recherché", ["Duelist", "Controller", "Initiator", "Sentinel"])

    st.subheader("Candidats issus des équipes VCT rivales")
    vct_candidates = df_valid[
        (df_valid[role_col] == role) & (df_valid["team_full"] != team)
    ].copy()
    if "performance_index_role" in vct_candidates.columns:
        vct_candidates = vct_candidates.sort_values("performance_index_role", ascending=False)
    show_cols = [c for c in ["player", "team_full", "nationality", "rating", "performance_index_role", "is_igl"] if c in vct_candidates.columns]
    st.dataframe(vct_candidates[show_cols].head(10), use_container_width=True, hide_index=True)

    if data["composition_nationale"] is not None:
        nat_row = data["composition_nationale"][data["composition_nationale"]["team_full"] == team]
        if not nat_row.empty and bool(nat_row["roster_ferme"].values[0]):
            dom = nat_row["nationalite_dominante"].values[0]
            st.info(
                f"⚠️ Roster à dominante {dom} (≥80%) — un candidat d'une autre nationalité "
                f"est statistiquement moins probable pour cette équipe (heuristique, pas une règle)."
            )

    st.subheader("Candidats issus du vivier Challengers (VCL)")
    if data["pool_vcl"] is not None and not data["pool_vcl"].empty:
        vcl_candidates = data["pool_vcl"][data["pool_vcl"]["main_role"] == role].copy()
        vcl_candidates = vcl_candidates.sort_values("rating", ascending=False)
        show_cols_vcl = [c for c in ["player", "team_full", "nationality", "rating", "maps"] if c in vcl_candidates.columns]
        st.dataframe(vcl_candidates[show_cols_vcl].head(10), use_container_width=True, hide_index=True)
        st.caption(
            "⚠️ Niveau VCL, pas directement comparable à un rating VCT — sert à repérer des "
            "profils à surveiller, pas à comparer brut à brut."
        )
    else:
        st.caption("Pas de feuille 'Pool Challengers VCL' dans ce fichier — lance la Partie 4 du notebook pour l'obtenir.")

    if data["transferts"] is not None and not data["transferts"].empty:
        st.subheader("Spéculations de transfert déjà calculées (section 17 du notebook)")
        tdf = data["transferts"]
        tdf_filtered = tdf[(tdf.get("role") == role) & (tdf.get("equipe_cible") == team)] if "role" in tdf.columns else tdf
        st.dataframe(tdf_filtered, use_container_width=True, hide_index=True)

# --------------------------------------------------------------------------
# PAGE 5 — Évolution multi-stage
# --------------------------------------------------------------------------
elif page == "Évolution multi-stage":
    st.title("Évolution des équipes et des joueurs")

    if data["historique_3_stages"] is None:
        st.warning(
            "Feuille 'Historique 3 stages' absente — lance la Partie 4 du notebook "
            "(Kickoff + Stage 1 + Stage 2) pour obtenir cette vue."
        )
    else:
        hist = data["historique_3_stages"]

        tab1, tab2 = st.tabs(["Par équipe", "Par joueur"])

        with tab1:
            team_avg = hist.groupby(["team_full", "stage_order", "stage"])["rating"].mean().reset_index()
            fig = px.line(
                team_avg.sort_values("stage_order"), x="stage", y="rating", color="team_full",
                markers=True, labels={"rating": "Rating moyen d'équipe", "stage": ""},
            )
            fig.update_layout(height=600)
            st.plotly_chart(fig, use_container_width=True)

            if data["tendance_equipes"] is not None:
                st.subheader("Pente de tendance (régression sur les 3 stages)")
                st.dataframe(
                    data["tendance_equipes"].sort_values("pente_tendance", ascending=False),
                    use_container_width=True, hide_index=True,
                )

        with tab2:
            players = sorted(hist["player"].dropna().unique())
            selected_players = st.multiselect("Joueurs à comparer", players, default=players[:5])
            if selected_players:
                pdf = hist[hist["player"].isin(selected_players)].sort_values("stage_order")
                fig2 = px.line(
                    pdf, x="stage", y="rating", color="player", markers=True,
                    labels={"rating": "Rating", "stage": ""},
                )
                fig2.update_layout(height=500)
                st.plotly_chart(fig2, use_container_width=True)

    if data["bilan_roster"] is not None:
        st.subheader("Bilan des changements de roster Stage 1 → Stage 2")
        st.dataframe(data["bilan_roster"], use_container_width=True, hide_index=True)
