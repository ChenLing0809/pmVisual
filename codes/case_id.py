import pandas as pd

df_original = pd.read_csv("../data/BPI Challenge 2017.csv")
case_list = pd.DataFrame(df_original['case:concept:name'].unique())
case_list.to_csv("../data/case_list.csv")