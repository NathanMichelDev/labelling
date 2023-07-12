import streamlit as st
import pandas as pd
import random
import string
import json

from google.cloud import firestore
from google.oauth2 import service_account

key_dict = json.loads(st.secrets["textkey"])
creds = service_account.Credentials.from_service_account_info(key_dict)
db = firestore.Client(credentials=creds, project=creds.project_id)


def create_random_id():
    return "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(20)
    )


def get_labels():
    label_docs = db.collection("Label").stream()
    list_label_df = []
    for label_doc in label_docs:
        label_df = pd.DataFrame(label_doc.to_dict(), index=[0])
        list_label_df.append(label_df)
    if list_label_df:
        labels = (
            pd.concat(list_label_df, ignore_index=True)
            .drop_duplicates()
            .reset_index(drop=True)
        )[["trip_id", "label", "details"]]
    else:
        labels = pd.DataFrame(columns=["trip_id", "label", "details"])
    return labels


if "labels" not in st.session_state:
    st.session_state.labels = get_labels()

trip_id = st.text_input("Enter your trip id")
if trip_id:
    label_type = st.radio("Label type", ("Tandem", "Tandem partiel", "Solo", "Autre"))
    details = st.text_input("Enter details")

    if st.button("Submit") == True:
        if len(trip_id) != 20:
            st.error("Invalid trip id lenght.")
            st.stop()
        if details == "" and label_type == "Autre":
            st.error("Please enter details if you select Autre")
            st.stop()

        if (
            st.session_state.labels.query(
                "trip_id == @trip_id and label == @label_type"
            ).shape[0]
            > 0
        ):
            st.error("This trip id already has this label")
            st.stop()

        label = {
            "trip_id": trip_id,
            "label": label_type,
            "details": details,
        }

        random_id = create_random_id()
        db.collection("Label").document(random_id).set(label)
        st.session_state.labels = get_labels()
        if trip_id in st.session_state.labels["trip_id"].values:
            st.success(f"Label {label_type} added successfully to trip {trip_id}")
            st.balloons()
        else:
            st.error("Something wrong happened..")
