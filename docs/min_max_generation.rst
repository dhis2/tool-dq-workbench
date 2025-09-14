Min-max generation
==================

Min-max values in DHIS2 are used to define acceptable ranges for data values.
Values that fall outside these ranges will be flagged in the data entry app, helping to ensure data quality and accuracy.
Data values can certainly fall outside these ranges for valid reasons, but having these checks in
place helps to catch potential data entry errors. Users should received appropriate training on how to interpret
and handle values that fall outside the defined min-max ranges.

The DQ Monitor application provides a way to automatically generate and update these min-max ranges based on historical data.
This section describes how to generate min-max ranges for data values in a DHIS2 instance using the DQ Monitor application.


Editing a min-max generation stage
----------------------------------

To define a new min-max generation stage, press the *DQ monitor* link in the left menu, and then click *New min-max generation stage*.
You will be presented with a form to fill in the details of the min-max generation stage. Each of the fields is
described in the next section.

``Stage name``
   The name of the min-max generation stage.

``Completeness threshold``
   The completeness threshold defines the minimum ratio of data values that must be present for any given
   data element + category option combination + org unit combination to be considered for min-max generation.
   The threshold is specified as a ratio (0-1). For example, if the completeness threshold is set to 0.8,
   and there are 12 periods in the analysis duration, then at least 10 data values must be present for that
   combination to be considered for min-max generation. Setting a higher completeness threshold helps ensure
   that the generated min-max ranges are based on sufficient data, reducing the risk of generating ranges based
   on sparse or incomplete data.

``Missing data minimum and maximum values``
   The missing data minimum and maximum values are used to fill in for missing data values when calculating the min-max ranges.
   These values are used when data values are either missing or when the completeness threshold is not met. The values set here
   will be used in place of any missing data values to ensure that the min-max calculation can proceed. For example, if the
   missing data minimum is set to 0 and the missing data maximum is set to 1000, then any missing data values will be treated
   as having a value of 0 for the minimum calculation and a value of 1000 for the maximum calculation. Users should choose these
   values carefully so that they do not result in a large number of false positive values being flagged as min-max violations.
   Realistically, zero is often a good choice for the minimum, since with most aggregate data in DHIS2, negative values are not
   expected (although this will depend on the specific use case). For the maximum, users should choose a value that is higher than
   any expected data value, but not so high that it would rarely be exceeded. For example, if the expected data values are typically
   in the range of 0-100, then a missing data maximum of 500 could be a reasonable choice. This would ensure that severe outliers are
   still flagged, while avoiding excessive false positives.

``Previous periods``
    The number of previous periods to include in the min-max calculation. This defines the historical data window that will be used
    to calculate the min-max ranges. For example, if the analysis period is monthly and the number of previous periods is set to 12,
    then the min-max calculation will consider data from the past 12 months.

``Datasets``
   The datasets to include in the min-max generation. Only data elements which have a numeric value type
   that are part of the selected datasets will be considered for min-max generation.

``Data element groups (optional)``
   The data element groups to include in the min-max generation. If no data element groups are selected, then all numeric
   data elements in the selected datasets will be considered for min-max generation. If one or more data element groups are
   selected, then only data elements that are part of at least one of the selected groups will be considered for min-max generation.


``Data elements (optional)``
   Similar to data element groups, the data elements field allows users to further refine the selection of data elements to be
   considered for min-max generation. If no data elements are selected, then all numeric data elements in the selected datasets
   (and data element groups, if any are selected) will be considered for min-max generation. If one or more data elements are
   selected, then only those specific data elements will be considered for min-max generation.


``Organisation units``
   The organisation units to include in the min-max generation. Only data values reported for the selected organisation units
   (or their descendants, if the "Include descendants" option is selected) will be considered for min-max generation. You may need
   to experiment with different levels of organisation units. Using lower level organisation units will result in more data queries
   to the server (each smaller in size but more numerous), while using higher level organisation units (e.g. national) will result in
   fewer data queries (which may be larger in size). The optimal choice will depend on the specific DHIS2 instance and its data volume.

   Alternatively, you may only wish to calculate min-max values for a specific set of organisation units. In this case, you can select
   the specific organisation units to include in the min-max generation.

``Min-max groups``
    Groups are used to define the method for calculating the min-max values. Each group specifies a statistical method, a limit median,
    and a threshold used to calculate the min-max values

``Limit median``
   The limit median is used to select which of the groups which you defined will be used to calculate the min-max values.
   For instance, if you have a set of values like [10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30], the median is 20. The group
   which has the limit median closest to 20 (but not greater than 20) will be used to calculate the min-max values.

``Threshold``
   The threshold is used in conjunction with the statistical method defined in the group to calculate the min-max values.
   For example, if the statistical method is "Standard Deviation" and the threshold is 2, then the min-max values will be calculated
   as the mean plus or minus 2 times the standard deviation.

``Statistical methods```

Previous max
    The previous max method sets the max value to the maximum value observed in the historical data window times
    the threshold. As an example, if the maximum value observed is 100, and the threshold is 1.2, then the max value will be set to 120.
    The min value is set to max values times one minus the threshold or zero, which ever is greater. This method is often useful for data
    elements where the values are expected to be non-negative and where the maximum value is a good indicator of the expected range of values.
    The threshold can be used to allow for some variation above the historical maximum in order to avoid excessive false positives.

Z-score
    The z-score method sets the min and max values based on the mean and standard deviation of the historical data window.
    The min value is set to the mean minus the threshold times the standard deviation, and the max value is set to the mean plus
    the threshold times the standard deviation. This method is useful for data elements where the values are expected to be normally
    distributed around a mean value. The threshold can be used to control how many standard deviations away from the mean are considered acceptable.

MAD (Median absolute deviation)
    The MAD method sets the min and max values based on the median and median absolute deviation of the historical data window.
    The min value is set to the median minus the threshold times the median absolute deviation, and the max value is set to the median
    plus the threshold times the median absolute deviation. This method is useful for data elements where the values may not be normally
    distributed and where outliers may be present. The threshold can be used to control how many median absolute deviations away from
    the median are considered acceptable.

Box-Cox
    The Box-Cox method is a transformation-based approach that aims to stabilize variance and make the data more normally distributed.
    The min and max values are calculated based on the transformed data using the Box-Cox transformation, with the threshold controlling
    how many standard deviations away from the mean of the transformed data are considered acceptable. This method is useful for data elements
    where the values may be skewed or have a non-constant variance. The Box-Cox transformation can help to make the data more suitable for
    statistical analysis. Box-Cox requires that all data values be positive, so if your data contains zero or negative values, a transformation
    of the data will be applied automatically in order to shift all values to be positive. Once the min-max values are calculated, they will be shifted back
    to the original scale.

IQR (Interquartile range)
   The IQR method sets the min and max values based on the first and third quartiles of the historical data window.
   The min value is set to the first quartile minus the threshold times the interquartile range (IQR), and the max value is set to the third
   quartile plus the threshold times the interquartile range. This method is useful for data elements where the values may not be normally
   distributed and where outliers may be present. The threshold can be used to control how far outside the interquartile range are considered acceptable.
