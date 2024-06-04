import streamlit as st
import gspread
import pandas as pd
import json
import time

from google.oauth2 import service_account

st.set_page_config(
    layout="wide",  # Can be "centered" or "wide". In the future also "dashboard", etc.
    page_title="Studend project",  # String or None. Strings get appended with "• Streamlit".
    page_icon="🗒️",  # String, anything supported by st.image, or None.
)


def get_creds():
    return service_account.Credentials.from_service_account_info(
        json.loads(st.secrets["textkey"]),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
        ],
    )


def get_sheet(creds) -> gspread.spreadsheet.Spreadsheet:
    return gspread.authorize(creds).open_by_url(st.secrets["students_url"])


def get_result_dataframe(sheet: gspread.spreadsheet.Spreadsheet) -> pd.DataFrame:
    result_worksheet = sheet.worksheet("result")
    return pd.DataFrame(result_worksheet.get_all_records())


def check_csv_format(dataframe: pd.DataFrame, result_dataframe: pd.DataFrame) -> bool:
    columns = dataframe.columns.tolist()
    if columns != ["trip_id", "label"]:
        st.error(
            f"Wrong columns. Expected ['trip_id', 'label'], got {columns}. "
            f"Please upload a CSV file with the correct format."
        )
        return False
    # Check if the dataframe has good length
    if len(dataframe) != len(result_dataframe):
        st.error(
            f"Wrong number of rows. Expected {len(result_dataframe)}, got {len(dataframe)}. "
            f"Please upload a CSV file with the correct format."
        )
        return False
    trips = dataframe["trip_id"].unique().tolist()
    expected_trips = result_dataframe["trip_id"].tolist()
    missing_trips = set(expected_trips) - set(trips)
    if missing_trips:
        st.error(
            f"Missing trips: {missing_trips}. Please upload a CSV file with all trips."
        )
        return False
    non_expected_trips = set(trips) - set(expected_trips)
    if non_expected_trips:
        st.error(
            f"Non expected trips: {non_expected_trips}. Please upload a CSV file with only trips from test dataset."
        )
        return False
    labels = set(dataframe["label"].unique().tolist())
    expected_labels = set(result_dataframe["label"].tolist())
    unexpected_labels = labels - expected_labels
    if unexpected_labels:
        st.error(
            f"Unexpected labels: {unexpected_labels}. Please upload a CSV file with only labels from test dataset: {expected_labels}."
        )
        return False
    return True


# Ask for a token
if "token" not in st.session_state:
    token = st.text_input("Enter your token")

    if not token:
        st.stop()

    if token in st.secrets["tokens"]:
        st.success("Token is valid")
        st.session_state["token"] = token
        # Sleep 2 seconds
        time.sleep(2)
        st.rerun()
    else:
        st.error("Token is invalid")
        st.stop()

st.header("Welcome to the student project")
worksheet_name = st.session_state["token"]

# Load the credentials & sheet details from streamlit secrets
creds = get_creds()
sheet = get_sheet(creds)
result_dataframe = get_result_dataframe(sheet)


def merge_result_predictions(
    dataframe: pd.DataFrame, result_dataframe: pd.DataFrame
) -> pd.DataFrame:
    # Merge the two dataframes
    merged_dataframe = pd.merge(
        dataframe, result_dataframe, on="trip_id", suffixes=("_student", "_result")
    )
    return merged_dataframe


def compute_score(merged_dataframe: pd.DataFrame) -> float:
    # Transform the labels to float
    merged_dataframe = merged_dataframe.replace(
        {"Chute": 1, "Manipulation": 0.8, "Chute vélo seul": 0.8, "Pas de chute": 0}
    )

    merged_dataframe["error"] = (
        abs(merged_dataframe["label_student"] - merged_dataframe["label_result"]) ** 2
    )
    score = (1 - merged_dataframe["error"].mean()) * 100
    return score


# Check if the worksheet name exists
if worksheet_name in [sheet.title for sheet in sheet.worksheets()]:
    st.info("You have already submitted your predictions.")
    # Load the sheet as dataframe
    worksheet = sheet.worksheet(worksheet_name)
    df = pd.DataFrame(worksheet.get_all_records())
    st.write(f"Your predictions:")
    st.write(df)
    # Compute the results
    merged_dataframe = merge_result_predictions(df, result_dataframe)
    # score = compute_score(merged_dataframe)
    # st.write(f"Your score is: {score}")
    # Compute the confusion matrix
    confusion_matrix = pd.crosstab(
        merged_dataframe["label_student"], merged_dataframe["label_result"]
    )
    st.write("Confusion matrix:")
    st.write(confusion_matrix)
    # Compute the score (sum of the diagonal)
    score = (
        1 - confusion_matrix.values.diagonal().sum() / confusion_matrix.values.sum()
    ) * 100
    st.write(f"Your score is: {score.round(2)}%")
    st.stop()

# # Create a new worksheet
# worksheet = st.session_state.sheet.add_worksheet(
#     title=worksheet_name, rows=1, cols=1
# )

# Ask user to load a csv
st.write("Upload your predictions as a CSV file.")
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    # save csv as sheet
    df = pd.read_csv(uploaded_file)

    # Check if the format is good
    if not check_csv_format(df, result_dataframe=result_dataframe):
        st.stop()

    # Add a worksheet
    sheet = sheet.add_worksheet(title=worksheet_name, rows=1, cols=1)
    sheet.update([df.columns.values.tolist()] + df.values.tolist())
    st.write("Data uploaded successfully")
    time.sleep(2)
    st.rerun()
