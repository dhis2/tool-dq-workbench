# Validation Rule Monitoring App for DHIS2

## Overview
The Data Quality Workbench is a server-side app designed for use with DHIS2. 
This app focuses on improving data quality by monitoring and analyzing validation rules, outliers
and metadata inconsistencies. The app is also capable of helping you to generate min-max values
for your data.

The app has a user interface that will help you to create a configuration file. This configuration file can consist
of multiple stages. Once you have created the configuration file, a command line script can be scheduled to run daily.

From a high level, the app will:
1. Retrieve validation rule violations, outliers and metadata integrity checks from DHIS2 for a specified time period.
2. The number of issues for a given organisation will be counted, and transformed into a numeric value. 
3. This numeric value will be stored in DHIS2 as a normal data element value.

### What are Validation Rules in DHIS2?
Validation rules in DHIS2 are logical checks applied to reported data to ensure accuracy and consistency. 
As an example, consider a health facility that reports HIV testing data. A validation rule for this scenario could be:

```
The number of people testing positive for HIV must be less than or equal to the number of people who were tested for HIV.
```

In this case, both the number of people tested and the number of people testing positive are reported to DHIS2. The validation rule ensures that the reported data is internally consistent and accurate with respect to other data values. If the number of people tested is lower than the number of people who test positive, this will lead to indicator calculations greater than 100%, which is a data quality problem. 

## Problem Statement
Validation rule violations often occur due to incomplete or incorrect data reporting. For instance, a clinic may report the number of people testing positive for HIV but fail to report the total number tested. Such inconsistencies:

- Compromise data quality.
- Lead to delays in analysis and decision-making.
- Require systematic monitoring to identify and resolve.

Previously, analyzing validation rules in DHIS2 was limited to the data quality app or via the data entry screen. This  data quality app is quite limited in that it is only capable of displaying a list of no more than 500 violations. Visualization of data quality hotspots, trends over time, and tracking of resolution progress are not possible with the data quality app.

The Validation Rule Monitoring Tool helps to  address some of these challenges by:

1. Identifying validation rule violations over a defined time period (e.g., last 12 months).
2. Capturing a snapshot of the current status of these violations. The script is meant to be run once a day and will capture the current status of a group of validation rules.
3. This snapshot value is then stored in DHIS2 as a  normal data element value.
4. Tracking the resolution status of these violations over subsequent days can be accomplished by using the native DHIS2 analysis tools such as maps, graphs, and pivot tables. As the value of the validation rule snapshot data element is updated daily, it is possible to track the resolution status of the validation rule violations over time. Ideally, the value of the data element used to track the validation rule violations should be 0%, indicating that there are no validation rule violations. A value of 100% would indicate that over the given time period and validation rules checked, that all the validation rules have violations.


### Core Functionality of the Tool

1. **Data Collection and Transformation**
   The tool retrieves validation rule violations from DHIS2 for a specified time period for a defined validation rule group for a single organisation unit. While this may not seem particularly effecient, In order to illustrate this, lets consider the following example validation rule group called "ANC Data Quality" which consists of two validation rules:
     - The number of ANC2 visits should be less than or equal to the number of ANC1 visits.
     - The number of ANC3 visits should be less than or equal to the number of ANC2 visits.
   - In the configuration file, we can define multiple stages of the data quality process and define validation rules for each stage. Each stage should consist of the following:
     - A name for the stage.
     - A duration for which the validation rules should be checked, e.g. 12 months.
     - A level of the hierarchy for which the validation rules should be checked, e.g. facility. 
     - The validation rule group to check for this stage.
     - A data element to store the snapshot value.

In this example, there are two validation rules that are checked for the ANC Data Quality stage. The tool will request the status of these validation rules over the time period specified, and at each level of the hierarchy which has been defined in the configuration file. The maximum theoretical validation rule violations for this validation rule group is 24, as there are two validation rules in the group which are checked for 12 months. In the ideal scenario, the value of this data element should be 0, indicating that there are no validation rule violations. In order to calculate the value to be monitored, the app will count the number of validation rule violations for each validation rule in the group and sum them up, and then convert this to a percentage value relative to the maximum theoretical value. A value of 0% will be used to express that there are **no** validation rule violations, while a value of 100% will be used to express that all possible validation rules have violations. While this rather arbitrary percentage may not seem intuitive, it is a way to express the data quality in a single value, with 0% being the best possible value and 100% being the worst possible value.

2. **Snapshot Analysis**

As explained in the previous section, a percentage value representing the status of validation rule violations over a defined period of time will be stored as a data value. Since the tool will create a daily snapshot value for each data element, it is possible to track the resolution status of the validation rule violations over time. As an example, lets say that Facility X has an initial value of 600% for the "ANC Data Quality Snapshot" data element.  Over the next few days, the data managers at Facility X work to resolve these validation rule violations. When the new snapshot value is calculated a few days later and all of the validation rule violations have been resolved, the value of the "ANC Data Quality Snapshot" data element will be 0%. This indicates that there are no validation rule violations for the ANC Data Quality validation rule group at Facility X.

3. **Resolution Tracking**
   - The app tracks the status of validation rule violations over subsequent days.
   - It identifies whether violations are resolved, persist, or increase in frequency.

By allowing for the tracking of the resolution status of validation rule violations over time, the app can help to identify patterns or recurring problems in data entry processes. This can help data managers to identify areas where additional training or support is needed. By using analysis tools such as maps and pivot tables, higher-level managers can identify facilities or regions where data quality is particularly poor and take corrective action.

### Expected Outcome

In the ideal scenario, validation rule violations are resolved within a few days. The app helps to:

- Highlight persistent issues that require attention.
- Identify patterns or recurring problems in data entry processes.
- Facilitate timely corrective actions by data managers.

## Key Features

### 1. Automated Monitoring
The app automates the process of checking validation rule violations, reducing the need for manual intervention.

### 2. Historical Analysis
It provides a historical view of validation rule violations, allowing users to identify trends and recurring issues.

### 3. Reporting and Alerts
The app generates reports and notifications to inform users about unresolved violations, helping prioritize corrective actions.

### 4. Integration with DHIS2
Designed to work seamlessly with DHIS2, the app leverages its API to fetch and process validation rule data.

## Use Case Example

### Scenario

A clinic reports the following data for the month of January:

- **Number of people tested for HIV:** Not reported.
- **Number of people testing positive for HIV:** 15.

### Issue Detected

The validation rule “The number of people testing positive for HIV must be less than or equal to the number tested” is violated.

### App Workflow

1. The app detects this violation during its daily check.
2. The violation is logged in the 12-month snapshot.
3. Over the next few days, data managers update the missing information:
   - **Number of people tested for HIV:** 50.
4. The app marks the violation as resolved and updates its tracking.

### Result

- Improved data accuracy.
- Clear accountability for resolving data quality issues.

## Benefits

### For Data Managers

- Quick identification of incomplete or incorrect data.
- Automated tracking reduces the need for manual checks.

### For Decision-Makers

- Reliable, high-quality data for analysis and planning.
- Insights into recurring data quality issues for targeted training or process improvements.

### For the Organization

- Enhanced trust in reported data.
- Streamlined workflows for resolving data quality issues.

## Installation and Configuration

1. **Prerequisites:**
   - DHIS2 instance with API access.
   - Server environment for running the app.

2. **Setup Instructions:**
   - Deploy the script on your server.
   - Configure API access with appropriate credentials.
   - Define the validation rules to monitor.

3. **Usage:**
   - Schedule the script to run daily or at desired intervals.
   - Access reports through the app’s output interface.

## Future Enhancements

The app is designed to evolve based on user feedback. Potential features include:

- Dashboards for real-time visualization of validation rule violations.
- Integration with messaging systems for alerts.
- Support for custom validation rules.

## Conclusion

The Validation Rule Monitoring App empowers organizations to maintain high data quality standards in DHIS2 by automating the detection and tracking of validation rule violations. By ensuring data consistency and accuracy, the app supports better decision-making and improved health outcomes.

## Setup Instructions

### 1. Clone the Repository

```bash
git clone 