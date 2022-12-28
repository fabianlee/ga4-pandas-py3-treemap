#!/usr/bin/env python3
"""
 Example showing how to build a TreeMap with plotly library using Pandas DataFrame 
"""

#
# from inside venv:
# pip3 install pandas plotly kaleido
# pip3 freeze | tee requirements.txt
#
import sys
import traceback
import argparse

# pandas and plotly
import pandas as pd
import plotly.express as px

def main():

  # construct hierarchial Pandas DataFrame of petstore sales
  # two categories: mammals and reptiles
  # treemap area = absolute count of 'sales'
  # treemap color = change in sales count 'sales_delta'
  # 
  df = pd.DataFrame()

  # add reptiles to dataframe
  df_newrows = pd.DataFrame({"category":["reptile","reptile","reptile"],"sales":[1,2,4],"sales_delta":[-2,0,5],"name":["snake","lizard","turtle"]})
  # 'append' is being deprecated, so use pd.concat instead
  #df = df.append(dfp,ignore_index=True)
  df = pd.concat([df,df_newrows],ignore_index=True)

  # add mammals to dataframe
  df_newrows = pd.DataFrame({"category":["mammal","mammal"],"sales":[8,1],"sales_delta":[10,-3],"name":["dog","cat"]})
  df = pd.concat([df,df_newrows],ignore_index=True)

  # show full dataframe
  print(df)

  # https://plotly.com/python-api-reference/generated/plotly.express.treemap.html
  fig = px.treemap(
    data_frame=df,
    path=['category','name'],
    labels='name',
    values='sales',
    color='sales_delta',
    color_continuous_scale='blues' # https://plotly.com/python/builtin-colorscales/
    ) 

  # export html with mouse rollover and click-in detail
  fig.write_html("/tmp/petstore-treemap.html")
  # export simple image
  fig.write_image("/tmp/petstore-treemap.png")

if __name__ == '__main__':
  main()
