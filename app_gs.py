import streamlit as st
import gspread
import pandas as pd
import json
from datetime import datetime as date

from google.oauth2 import service_account


def get_creds():
    return service_account.Credentials.from_service_account_info(
        json.loads(st.secrets["textkey"]),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
        ],
    )


def get_sheet(sheet_url, sheet_name):
    return (
        gspread.authorize(st.session_state.creds)
        .open_by_url(sheet_url)
        .worksheet(sheet_name)
    )


def get_trips(sheet):
    labels = sheet.get_all_values()
    trips = []
    for label in labels[1:]:
        trips.append(label[0])
    return trips


def insert_row(
    sheet: gspread.Worksheet,
    trip_id: str,
    env: str,
    label_tandem: str,
    label_chute: str,
    assistance: int,
    user: str,
    details: str,
):
    # Load labelled trips to check for duplicates
    trips = get_trips(sheet)
    if trip_id in trips:
        st.error(
            "Le trajet a déjà été labellisé. Merci de modifier directement "
            "sur la feuille de calcul ou contactez l'équipe data."
        )
        return

    # Set new_index as 2 to insert the new row at the top of the sheet. The first row is the header.
    new_index = 2

    # Create the url to the trip in control with the appropriate environment
    url = f'=HYPERLINK(CONCATENATE("https://admin.", B{new_index},".fifteen.eu/trips/",A{new_index}),"URL")'

    # Create the new row to insert
    new_row = [
        trip_id,
        env,
        url,
        label_tandem,
        label_chute,
        assistance,
        user,
        details,
        False,
        date.now().strftime("%Y-%m-%d %H:%M:%S"),
    ]
    # Insert the new row at the top of the sheet
    sheet.insert_row(
        new_row,
        new_index,
        value_input_option="USER_ENTERED",  # for the URL
        inherit_from_before=True,  # Not sure if useful
    )


# Check if the user is authorized to access this page
if st.experimental_get_query_params().get("login", [""])[0] != st.secrets["login"]:
    st.error("You are not authorized to access this page")
    st.stop()

# Load the credentials & sheet details from streamlit secrets
if "creds" not in st.session_state:
    st.session_state.creds = get_creds()
sheet_url = st.secrets["sheet_url"]
sheet_name = st.secrets["sheet_name"]

# Boolean that keeps track if the form can be submitted
flag_can_insert = True

# Display the form
st.title("Labelisation des trajets")
st.header("Informations sur le trajet")
cols = st.columns(3)
with cols[0]:
    trip_id = st.text_input(
        "Id du trajet",
        value=st.experimental_get_query_params().get("trip_id", [""])[0],
    )
    if trip_id:
        if len(trip_id) != 20:
            st.info("L'id du trajet n'est pas correcte.")
            flag_can_insert = False
with cols[1]:
    environment = st.text_input(
        "Environnement",
        value=st.experimental_get_query_params().get("env", [""])[0],
    )
    if environment:
        if environment not in (
            "staging",
            "preprod",
            "prod",
            "partners",
            "omega",
            "sigma",
        ):
            st.info(
                "Environnement invalide. Les valeurs possibles sont staging, preprod, prod,"
                " partners, omega, et sigma."
            )
            flag_can_insert = False
with cols[2]:
    user_name = st.text_input("Votre nom (Optionel)")

# TANDEM
st.header("Tandem")
TANDEM_LABELS = {
    "Solo": "la quasi totalité de ce trajet a été réalisée seul(e).",
    "Tandem": "la quasi totalité de ce trajet a été réalisée à deux personnes.",
    "Tandem partiel": "une partie non négligeable de ce trajet a été réalisée à deux personnes.",
    "Ne sait pas": "vous ne vous souvenez pas.",
    "Autre": "aucun des labels ne correspond (précisez dans la rubrique détails).",
}
with st.expander("Plus d'infos sur les labels tandem", expanded=False):
    text = """
        Le label tandem permet de savoir si le trajet a été effectué par un ou deux utilisateurs. Il se peut que 
        vous n'ayez pas fait le trajet soit totalement seul soit totalement en tandem. Dans ce cas, sélectionnez
        soit **Tandem partiel** soit **Autre**, et apportez des précisions si besoin dans la rubrique détails.
        """
    for label in TANDEM_LABELS:
        text += f"\n- **{label}** : {TANDEM_LABELS[label]}"
    st.markdown(text)
cols = st.columns(2)
with cols[0]:
    label_tandem = st.selectbox(
        "Label tandem", [""] + list(TANDEM_LABELS.keys()), label_visibility="collapsed"
    )
with cols[1]:
    if label_tandem:
        st.info(f"**Vous avez indiqué que {TANDEM_LABELS[label_tandem]}**")
    else:
        st.warning("Vous n'avez pas renseigné ce champ.")

st.header("Chute")
CHUTE_LABELS = {
    "Pas de chute": "le vélo n'a jamais chuté (position horizontale).",
    "Chute": "vous étiez sur le vélo lors de la chute.",
    "Chute vélo": "le vélo est tombé alors que vous n'étiez pas dessus.",
    "Manipulation": "vous avez manipulé le vélo, et celui ci peut avoir été mis à l'horizontal.",
    "Ne sait pas": "vous ne vous souvenez pas de ce trajet.",
    "Autre": "aucun des labels ne correspond (précisez dans la rubrique détails).",
}
chute_text = """

    La labelisation pour la détection de chute est complexe. De manière générale, une chute est un évènement où le vélo
    est à l'horizontal. Il peut y avoir différents types de chutes :
    \n- à l'arrêt ou en mouvement,
    \n- vélo seul ou avec l'utilisateur.
    \n- volontaire (manipulation ou vandalisme) ou involontaire (accident).
    \nAfin de caractériser au mieux les chutes, il est crutial pour nous d'avoir le plus de précision possible lors de la 
    labelisation. En effet, nous voudrions pouvoir être capables de différencier et catégoriser 
    les chutes pour :
    - identifier les zones où la pratique du vélo est dangereuse (chute involontaire en mouvement avec utilisateur)
    - trouver les utilisateurs qui mettent les vélos au sol de manière répétitive (chute volontaire à l'arrêt sans utilisateur)
    et ne pas mélanger les deux catégories.
    \nPour cela, nous avons introduit les catégories suivantes :
    """
for label in CHUTE_LABELS:
    chute_text += f"\n- **{label}** : {CHUTE_LABELS[label]}"

with st.expander("Plus d'infos sur les labels de chute", expanded=False):
    st.markdown(chute_text)
cols = st.columns(2)
with cols[0]:
    label_chute = st.selectbox(
        "Label chute",
        [""] + list(CHUTE_LABELS.keys()),
        label_visibility="collapsed",
    )
with cols[1]:
    if label_chute:
        st.info(f"**Vous avez indiqué que {CHUTE_LABELS[label_chute]}**")
    else:
        st.warning("Vous n'avez pas renseigné ce champ.")

st.header("Qualité de l'assistance")
ASSIT_QUALITY_LABELS = {
    "RAS": "l'assistance a fonctionné correctement.",
    "Excellent": "l'assistance a été excellente.",
    "Bonne": "l'assistance a été bonne.",
    "Mauvaise": "l'assistance a été mauvaise.",
    "Médiocre": "l'assistance a été médiocre.",
    "Pas d'assistance": "vous n'avez pas eu d'assistance.",
    "Ne sait pas": "vous ne vous souvenez pas.",
}
cols = st.columns(2)
with cols[0]:
    assist_quality = st.selectbox(
        "Qualité de l'assistance",
        [""] + list(ASSIT_QUALITY_LABELS.keys()),
        label_visibility="collapsed",
    )
with cols[1]:
    if assist_quality:
        st.info(f"**Vous avez indiqué que {ASSIT_QUALITY_LABELS[assist_quality]}**")
    else:
        st.warning("Vous n'avez pas renseigné ce champ.")


details = st.text_area("Details (Optionel)")

if flag_can_insert:
    if st.button("Envoyer"):
        sheet = get_sheet(sheet_url, sheet_name)
        insert_row(
            sheet=sheet,
            trip_id=trip_id,
            env=environment,
            label_tandem=label_tandem,
            label_chute=label_chute,
            assistance=assist_quality,
            user=user_name,
            details=details,
        )
        st.success("Merci !")
else:
    st.error("Un champ du formulaire n'est pas correctement renseigné.")
