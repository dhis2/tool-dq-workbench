Min-max generation
==================

Min-max values in DHIS2 are used to define acceptable ranges for data values.
Values that fall outside these ranges will be flagged in the data entry app, helping to ensure data quality and accuracy.
Data values can certainly fall outside these ranges for valid reasons, but having these checks in
place helps to catch potential data entry errors. Users should received appropriate training on how to interpret
and handle values that fall outside the defined min-max ranges.

The DQ Monitor application provides a way to automatically generate and update these min-max ranges based on historical data.
This section describes how to generate min-max ranges for data values in a DHIS2 instance using the DQ Monitor application.


Editing an min-max generation stage
---------------------------------

To define a new min-max generation stage, press the *DQ monitor* link in the left menu, and then click *New min-max generation stage*.
You will be presented with a form to fill in the details of the min-max generation stage. Each of the fields is
described in the next section.

``Stage name``
   The name of the min-max generation stage.

``Completeness threshold``
   The completeness threshold defines the minimum ratio of data values that must be present for any given
   data element + category option combination + org unit combination
    to be considered for min-max generation. The threshold is specified as a ratio (0-1).
    For example, if the completeness threshold is set to 0.8, and there are 12 periods in the analysis duration,
    then at least 10 data values must be present for that combination to be considered for min-max generation.
    Setting a higher completeness threshold helps ensure that the generated min-max ranges are based on sufficient data,
    reducing the risk of generating ranges based on sparse or incomplete data.

``Missing data minimum and maximum values``
    The missing data minimum and maximum values are used to fill in for missing data values when calculating the min-max ranges.
    These values are used when data values are either missing or when the completeness threshold is not met. The values
    set here will be used in place of any missing data values to ensure that the min-max calculation can proceed.
    For example, if the missing data minimum is set to 0 and the missing data maximum is set to 1000, then any missing data values
    will be treated as having a value of 0 for the minimum calculation and a value of 1000 for the maximum calculation.
    Users should choose these values carefully so that they do not result in a large number of false positive values being flagged as
    min-max violations.  Realistically, zero is often a good choice for the minimum, since with most aggregate data in DHIS2,
    negative values are not expected (although this of course will depend on the specific use case). For the maximum, users should choose a value that is higher than any expected data value,
    but not so high that it would rarely be exceeded. For example, if the expected data values are typically in the range of 0-100,
    then a missing data maximum of 500 could be a reasonable choice. This would ensure that severe outliers are still flagged, while avoiding excessive false positives.


```Duration``
   The duration of the min-max generation stage. This is used to determine the start and end dates of the min-max generation analysis
   relative to the current date. The duration can be specified in days, weeks, months, or years with the format ``12 months``, ``3 weeks``, ``7 days``, etc.
   The type of period used here should match the period type of the data set used for the min-max generation analysis.
   For example, if the data set uses a monthly period type, you should use a duration of ``12 months`` to analyze the last 12 months of data.
   If you use a duration of ``3 weeks``, the min-max generation analysis will only analyze the last 3 weeks of data,
   which may not be sufficient to generate meaningful min-max ranges in a monthly data set.evel where the min-max generation analysis will be started. You may need to experiment with this