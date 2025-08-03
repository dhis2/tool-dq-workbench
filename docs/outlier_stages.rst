Outlier stages
// ===================================
// Outlier stages are used to detect outliers in the data. The data quality module can be used to identify individual
outliers, but with the DQ Workbench, you can summarize the number of outliers and store this as a data value
in DHIS2. To define a new stage, press the "DQ monitor" link in the left menu, and then click
"New outlier stage". You will be presented with a form to fill in the details of the outlier stage.

The form consists of the following fields:
- **Stage name**: The name of the outlier stage.
- **Org unit level**: This is the level where the outlier analysis will be started. You may need to experiment
with this setting to find the best fit for your data. The outlier analysis will be performed on all org units
    at the specified level and below. If you set the level to 1, a single request will be made to the DHIS2 API
for all org units. This may result in a set of results which is too large to be returned by the API.
If you set the level to 2, the outlier analysis will make a request
for each org unit at level 2 (including all of its children). Thus, you can set the orgunit level at a lower level
to increase the number of requests made to the DHIS2 API (which in turn should
reduce the overall number of individual outlier results returned),
but this will also increase the time it takes to run the outlier analysis.
- **Duration**: The duration of the outlier stage. This is used to determine the start and end dates of the outlier
analysis relative to the current date. The duration can be specified in days, weeks, months, or years with the
format `12 months`, `3 weeks`, `7 days`, etc.
- **Data set**: The data set to use for the outlier analysis.
- **Algorithm**: The algorithm to use for the outlier analysis. The available algorithms are:
  - **MOD_Z_SCORE**: Modified Z-score method.
  - **MIN_MAX**: Determines outliers based on the minimum and maximum values.
  - **Z_SCORE**: Z-score method.
  - **INVALID_NUMERIC**: Identifies invalid numeric values as outliers. These typically correspond to very large
    or very small values which cannot be cast to a number.
- **Threshold**: The threshold to use for the outlier analysis. This paramater is only relevant for the
  MOD_Z_SCORE and Z_SCORE algorithms. When the Z-score is above the threshold, the value is considered an outlier.
- **Destination data element**: The data element to used to store the number of outliers detected by the outlier stage.
- **Active**: Whether the outlier stage is active or not. If the outlier stage is not active, it will be excluded
when running the outlier analysis with the command line script.