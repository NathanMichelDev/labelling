import streamlit as st
import gspread
import pandas as pd
import json
from datetime import datetime as date

from google.oauth2 import service_account

st.set_page_config(
    layout="wide",  # Can be "centered" or "wide". In the future also "dashboard", etc.
    page_title="Labelling",  # String or None. Strings get appended with "• Streamlit".
    page_icon="🗒️",  # String, anything supported by st.image, or None.
)

ENVIRONMENTS = ["staging", "preprod", "prod", "partners", "omega", "sigma"]
TANDEM_LABELS = {
    "Solo": "Vous étiez seul(e) sur le vélo.",
    "Tandem": "Vous étiez deux sur le vélo.",
    "Tandem partiel": "Vous étiez deux sur le vélo une partie du trajet.",
    "Ne sait pas": "Vous ne vous souvenez pas.",
    "Autre": "Aucun des labels ne correspond (précisez dans la rubrique *Remarques*).",
}
TEXT_TANDEM = """
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
for label in TANDEM_LABELS:
    TEXT_TANDEM += f"\n- **{label}** : {TANDEM_LABELS[label]}"

CHUTE_LABELS = {
    "Pas de chute": "Le vélo n'a jamais chuté (position horizontale).",
    "Chute": "Vous étiez sur le vélo lors de la chute.",
    "Chute vélo seul": "Le vélo est tombé alors que vous n'étiez pas dessus.",
    "Manipulation": "Vous avez manipulé le vélo, et celui ci peut avoir été mis à l'horizontal.",
    "Ne sait pas": "Vous ne vous souvenez pas de ce trajet.",
    "Autre": "Aucun des labels ne correspond (précisez dans la rubrique *Remarques*).",
}
TEXT_CHUTE = """
    Le label tandem permet de savoir si le trajet a été effectué par un ou deux utilisateurs. Il se peut que 
    vous n'ayez pas fait le trajet soit totalement seul soit totalement en tandem. Dans ce cas, sélectionnez
    soit **Tandem partiel** soit **Autre**, et apportez des précisions si besoin dans la rubrique *Remarques*.
    """
for label in CHUTE_LABELS:
    TEXT_CHUTE += f"\n- **{label}** : {CHUTE_LABELS[label]}"

ASSIT_QUALITY_LABELS = {
    "RAS": "Rien à signaler par rapport à d'habitude.",
    "Plus agréable": "L'assistance a été plus agréable que d'habitude.",
    "Moins agréable": "L'assistance a été moins agréable que d'habitude.",
    "Pas d'assistance": "Vous n'avez pas eu d'assistance.",
    "Ne sait pas": "Vous ne vous souvenez pas.",
}
TEXT_ASSIT_QUALITY = """
    Nous faisons des tests sur l'assistance des vélos, en particulier pour diminuer la consommation en trajet. 
    Il est important de conserver un bon ressenti utilisateur. Pour cela, nous avons besoin de savoir comment
    vous avez jugé l'assistance sur votre trajet.
    """
for label in ASSIT_QUALITY_LABELS:
    TEXT_ASSIT_QUALITY += f"\n- **{label}** : {ASSIT_QUALITY_LABELS[label]}"


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
        "Front",
        date.now().strftime("%Y-%m-%d %H:%M:%S"),
    ]
    # Insert the new row at the top of the sheet
    sheet.insert_row(
        new_row,
        new_index,
        value_input_option="USER_ENTERED",  # for the URL
        inherit_from_before=False,  # Keep the formatting of the next row
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

# Display the form
st.header("Context du trajet")
cols = st.columns(9)
with cols[0]:
    trip_id = st.text_input(
        "Id du trajet",
        value=st.experimental_get_query_params().get("trip_id", [""])[0],
    )

with cols[1]:
    if st.experimental_get_query_params().get("env", [""])[0] in ENVIRONMENTS:
        idx = ENVIRONMENTS.index(st.experimental_get_query_params().get("env", [""])[0])
    else:
        idx = 0
    environment = st.selectbox("Environnement", ENVIRONMENTS, index=idx)
with cols[2]:
    user_name = st.text_input("Votre nom (Optionel)")
if not trip_id:
    st.info("Veuillez renseigner l'id du trajet.")
    st.stop()
else:
    if len(trip_id) != 20:
        st.error("L'id du trajet n'est pas valide.")
        st.stop()
    else:
        url = f"https://control.{environment}.fifteen.eu/trips/{trip_id}"
        with cols[3]:
            st.write(f"[Voir le trajet sur Control]({url})")

st.header("Information sur le trajet")
cols = st.columns(4)
with cols[0]:
    label_tandem = st.selectbox("Tandem", list(TANDEM_LABELS.keys()))
    st.info(f"**{TANDEM_LABELS[label_tandem]}**")
with cols[1]:
    label_chute = st.selectbox("Chute", list(CHUTE_LABELS.keys()))
    st.info(f"**{CHUTE_LABELS[label_chute]}**")
with cols[2]:
    assist_quality = st.selectbox(
        "Qualité de l'assistance",
        list(ASSIT_QUALITY_LABELS.keys()),
    )
    st.info(f"**{ASSIT_QUALITY_LABELS[assist_quality]}**")
with cols[3]:
    details = st.text_area("Remarques (Optionel)")
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

st.markdown("---")
# TANDEM
st.header("Signification des labels")
cols = st.columns(3)
with cols[0]:
    with st.expander("Tandem", expanded=False):
        st.markdown(TEXT_TANDEM)
with cols[1]:
    with st.expander("Chute", expanded=False):
        st.markdown(TEXT_CHUTE)
with cols[2]:
    with st.expander("Qualité de l'assistance", expanded=False):
        st.markdown(TEXT_ASSIT_QUALITY)
