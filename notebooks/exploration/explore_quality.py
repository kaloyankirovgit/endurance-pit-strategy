# %%
from endurance_strategy.io.load import load_race_csv
from endurance_strategy.paths import race_path

df = load_race_csv(race_path("2025_LE_MANS"))
df.shape

# %%
list(df.columns)

# %%
df[df["NUMBER"] == "007"][["event_key", "NUMBER", "LAP_NUMBER", "ELAPSED_S"]].head(10)

# %%
one_car = df[df["NUMBER"] == "007"]
one_car["ELAPSED_S"].diff().head(10)

# %%
step = df.groupby(["event_key", "NUMBER"])["LAP_NUMBER"].diff()
step.value_counts(dropna=False)

# %%
from endurance_strategy.validation import quality

quality.find_duplicate_laps(df)
