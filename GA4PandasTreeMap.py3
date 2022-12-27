#!/usr/bin/env python3
"""
 Calculates growth and trends for unique page counts from Analytics Data API v1 (newer GA4 model)
 Uses gapandas4 library so we can use Pandas DataFrames
 Uses plotly to construct TreeMap hierarchial visualizations based on category and year

 Hierarchial data for TreeMap constructed assuming:
   * WordPress Settings > Permanlinks slugs '/%year%/%monthnum%/%day%/%postname%/'
   * The first word of the Page title slug is the category

 Starting point attribution:
 https://developers.google.com/analytics/devguides/reporting/data/v1/quickstart-client-libraries
"""

#
# from inside venv:
# pip3 install google-analytics-data
# pip3 install --upgrade oauth2client
# pip3 install gapandas4
# pip3 install tabulate
# pip3 install plotly kaleido
# pip3 freeze | tee requirements.txt
#
import sys
import traceback
import argparse

import gapandas4 as gp
# used for 'to_markdown' on DataFrame
import tabulate

import pandas as pd
import plotly.express as px

def build_filter_expression():
  """The Data API v1 can filter data during query, use this to exclude pagePath we do not want to consider"""

  # FILTER EXAMPLE#1: simple filter to show only pagePath containing 'kubernetes'
  #wp_pagefilter=gp.FilterExpression(
  #    filter=gp.Filter(field_name="pagePath",string_filter=gp.Filter.StringFilter(match_type=gp.Filter.StringFilter.MatchType.CONTAINS,value="kubernetes"))
  #  )

  # FILTER EXAMPLE#2: OR filter to show pagePath containing 'kubernetes' OR 'gke'
  #wp_pagefilter=gp.FilterExpression()
  #for to_include in ["kubernetes","gke"]:
  #  wp_pagefilter.or_group.expressions.append(gp.FilterExpression(
  #      filter=gp.Filter(
  #        field_name="pagePath",
  #        string_filter=gp.Filter.StringFilter(
  #          match_type=gp.Filter.StringFilter.MatchType.CONTAINS,
  #          value=to_include
  #        )
  #    )
  #  ))

  # FILTER EXAMPLE#3: exludes multiple wordpress special paths using NOT and AND
  wp_pagefilter=gp.FilterExpression()
  for to_exclude in ["/category","/tag/","/page/"]:
    wp_pagefilter.and_group.expressions.append(gp.FilterExpression(
      not_expression=gp.FilterExpression(
        filter=gp.Filter(
          field_name="pagePath",
          string_filter=gp.Filter.StringFilter(
            match_type=gp.Filter.StringFilter.MatchType.BEGINS_WITH,
            value=to_exclude
          )
        )
      )
    ))

  return wp_pagefilter


def get_unique_pagecount_report(jsonKeyFilePath,property_id,startDateStr,endDateStr):
    """Runs a report on a Google Analytics GA4 property."""

    # filter for Data API v1
    wp_pagefilter = build_filter_expression()

    # run request against Data API v1, GA4
    request = gp.RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[gp.Dimension(name="pagePath")],
        metrics=[gp.Metric(name="activeUsers")],
        date_ranges=[gp.DateRange(start_date=startDateStr, end_date=endDateStr)],
        dimension_filter=wp_pagefilter,
        order_bys=[ gp.OrderBy(metric = {'metric_name': 'activeUsers'}, desc = False) ]
    )
    # gp.Filter.StringFilter.MatchType.CONTAINS
    df = gp.query(jsonKeyFilePath,request,report_type="report")

    # removal of rows now done earlier (and more efficiently) with filter to Data API v1
    # filter out all rows that contain special chars, are wordpress special paths, or len<16
    #targets = ['?','&',"/category/","/page/","/tag/"]
    #df = df[df.apply(lambda r: any([not kw in r[0] for kw in targets]), axis=1)]

    # filter out rows with short path lengths
    # especially date paths from wordpress (e.g. /2017/08/31)
    df = df[df['pagePath'].str.len()>=16] # must be at least 16 chars or row thrown out!

    # ensure count is of type integer for sorting later
    df['activeUsers'] = df['activeUsers'].astype(str).astype(int)

    # construct 'year' column from first part of WordPress request path
    # assumes WordPress Settings > Permanlinks slugs '/%year%/%monthnum%/%day%/%postname%/'
    df = df.assign(year = lambda row: row['pagePath'].str[1:5] if row['pagePath'].str[1:3][0]=='20' else None)
    # this also works for parsing year from request path
    #df['year'] = df['pagePath'].str.split('/').str[1]

    # construct 'category' column from first word in WordPress Page slug
    # assumes the first word in your slug title is the category (e.g. 'kubernetes-*' or 'linux-*')
    # You could make this much smarter by looking up the actual WordPress 'Category'
    df = df.assign(simplePathIndex = lambda row: row['pagePath'].str[:-1].str.rfind('/')) # step1: find last occurence of '/'
    df = df.assign(simplePath = lambda row: row['pagePath'].str.slice(row['simplePathIndex'][0]+1)) # step2: extract page title slug
    df = df.assign(category = lambda row: row['simplePath'].str.split('-').str[0]) # step3: get first word of page title slug

    # sort by page count
    df = df.sort_values('activeUsers',ascending=False)

    # for debug, uses 'tabulate' module
    #print(df.to_markdown())

    return df

def synthesize_older_columns(response_latest,response_older):
  # do left join on pagePath, which gives us new count and old count in same dataframe
  response_latest = response_latest.merge(response_older,how='left',on='pagePath',suffixes=('','_old') )

  # synthesize delta (new-old) to see absolute winners/losers
  response_latest['delta'] = response_latest.apply(lambda row: row.activeUsers - row.activeUsers_old, axis=1)

  # sythesize delta percent (delta/new count) to see trends of growth
  #response_latest['delta'] = response_latest['delta'].ffill()
  response_latest['deltaPercent'] = response_latest.apply(lambda row: (row.delta/row.activeUsers)*100, axis=1)

  #print(response_latest.head())
  return response_latest


def main():

  examples = '''USAGE:
 jsonKeyFile googleGA4PropertyID [reportingDays=30]

 jsonKeyFile is the Google service account json key file
 googleGA4PropertyID can be seen by going to Google Analytics, Admin>Property Settings
 reportingDays is the number of days to rollup into reporting block (today-reportingDays)


 EXAMPLES:
 my.json 123456789
 my.json 123456789 14
'''
  
#  response_latest = pd.DataFrame()
#  dfp = pd.DataFrame({"category":["reptile","reptile","reptile"],"activeUsers":[1,1,1],"delta":[-2,0,5],"simplePath":["snake","allig","turtle"]})
#  response_latest = response_latest.append(dfp,ignore_index=True)
#  dfp = pd.DataFrame({"category":["mammal","mammal"],"activeUsers":[4,1],"delta":[10,-3],"simplePath":["dog","cat"]})
#  response_latest = response_latest.append(dfp,ignore_index=True)
#  print(response_latest)
#
#  fig = px.treemap(
#    data_frame=response_latest,
#    path=['category','simplePath'],
#    labels='simplePath',
#    values='activeUsers',
#    color='delta',
#    color_continuous_scale='blues' # https://plotly.com/python/builtin-colorscales/
#    ) 
#  fig.write_html("/tmp/delta.html")
#  sys.exit(0)

  # define arguments
  ap = argparse.ArgumentParser(description="Calculate growth/trends from Analytics",epilog=examples,formatter_class=argparse.RawDescriptionHelpFormatter)
  ap.add_argument('key', help="json key of Google service account")
  ap.add_argument('propertyId', help="GA4 propertyID from Google Analytics (Admin>Property Settings)")
  ap.add_argument('-d', '--days', default="30",help="number of days in reporting window")
  args = ap.parse_args()

  print(f"service account json={args.key}, Google Analytics propertyID={args.propertyId}, reporting window={args.days} days")
  #client = initialize_ga4_analyticsreporting(args.key)

  # get unique page counts per reporting day width
  ndays=int(args.days)
  response_latest = get_unique_pagecount_report(args.key, args.propertyId, startDateStr=f"{ndays}daysAgo", endDateStr="0daysAgo")
  response_older  = get_unique_pagecount_report(args.key, args.propertyId, startDateStr=f"{ndays*2}daysAgo", endDateStr=f"{ndays+1}daysAgo")
  print(f"lastest reporting window: 0daysAgo -> {ndays}daysAgo")
  print(f"older   reporting window: {ndays+1}daysAgo -> {ndays*2}daysAgo")
  print()

  # synthesize columns with older datapoints to construct delta and deltaPercent
  response_latest = synthesize_older_columns(response_latest,response_older)

  # get each unique parent category, populate row in dataframe
  for cats in response_latest.category.unique():
    cat_count = response_latest.loc[response_latest['category']==cats,'activeUsers'].sum()
    print(f"total sum of category {cats}={cat_count}")

    dfp = pd.DataFrame({"category":[""],"activeUsers":[cat_count],"activeUsers_old":[0],"pagePath":[cats],"simplePath":[cats]})
    response_latest = response_latest.append(dfp,ignore_index=True)

  # how many losers/winners to display
  nrows=25

  # sort by biggest absolute winners
  response_latest = response_latest.sort_values('activeUsers',ascending=False)

  # show losers and winners in terms of absolute hits
  print("====BIGGEST LOSERS======")
  print("delta,count,category,path")
  print(response_latest[['activeUsers','category','pagePath']].tail(nrows).to_string(index=False))

  print("====BIGGEST WINNERS======")
  print("delta,count,category,path")
  print(response_latest[['activeUsers','category','pagePath']].head(nrows).to_string(index=False))

  # sort by biggest percent winners to show trends
  response_latest = response_latest.sort_values('deltaPercent',ascending=False)
  # remove older entries that contain 'NaN' because that means we do not have enough data
  response_latest = response_latest.dropna(subset=['activeUsers_old','deltaPercent'])
  # make percentage human readable
  response_latest['prettyPercent'] = response_latest['deltaPercent'].astype(int).astype(str).add("%")

  # show losers and winners in terms of percent growth (% of total)
  print("====TRENDING DOWN======")
  print("growth%,category,newcount,oldcount,path")
  print(response_latest[['prettyPercent','category','activeUsers','activeUsers_old','pagePath']].tail(nrows).to_string(index=False))

  print("====TRENDING UP======")
  print("growth%,category,newcount,oldcount,path")
  print(response_latest[['prettyPercent','category','activeUsers','activeUsers_old','pagePath']].head(nrows).to_string(index=False))

  # create visualizations using plotly
  # https://plotly.com/python-api-reference/generated/plotly.express.treemap.html

  # treemap with hierarchy defined by 'category' = first word in page slug
  # area = absolute count of hits, color = change in count from last reporting window
  fig = px.treemap(
    data_frame=response_latest, 
    path=['category','simplePath'],
    labels='simplePath',
    values='activeUsers',
    color='delta',
    color_continuous_scale='blues' # https://plotly.com/python/builtin-colorscales/
    ) 
  fig.write_html("/tmp/GA4-treemap-category.html")
  fig.write_image("/tmp/GA4-treemap-category.png")

  # treemap with hierarchy defined by 'year' = assuming WordPress slug uses 4 digit year as first part of path
  # area = absolute count of hits, color = change in count from last reporting window
  fig = px.treemap(
    data_frame=response_latest, 
    path=['year','simplePath'],
    labels='simplePath',
    values='activeUsers',
    color='delta',
    color_continuous_scale='blues' # https://plotly.com/python/builtin-colorscales/
    ) 
  fig.write_html("/tmp/GA4-treemap-year.html")
  fig.write_image("/tmp/GA4-treemap-year.png")

if __name__ == '__main__':
  main()
