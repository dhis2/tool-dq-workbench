Integrity stages
================

An integrity stage records the number of metadata integrity violations for each
configured check as a daily snapshot in DHIS2. For example, the check
``Category options with no categories`` might report 4 violations today.
After the issues are resolved, the next run will store 0 — giving you a
trackable time series in DHIS2's standard analysis tools (Data Visualizer,
maps, pivot tables).

Create a new integrity stage
-----------------------------

Click **+ New Integrity Stage** from the main configuration screen. Only one
integrity stage is allowed per configuration.

``Stage name``
   A descriptive name for the stage.

``Monitoring data element group``
   A DHIS2 data element group whose members define which integrity checks to
   include. Each member must have a code matching ``MI_<check_code>``.
   See `Create missing integrity data elements`_ below for how to set this up.

``Dataset``
   The dataset used to store the integrity counts. The period type of this
   dataset determines how results are stored — a Monthly dataset overwrites the
   current month's value on each run, while a Daily dataset stores a new value
   each day.

``Active``
   If unchecked, this stage is skipped when running the CLI.

Create missing integrity data elements
---------------------------------------

The **Create missing integrity data elements** button in the stage form will
create a DHIS2 data element for every integrity check that does not already
have one. Data elements follow the naming convention ``[MI] <check name>``.

.. important::

   Newly created data elements are **not** automatically added to the monitoring
   data element group. After creation, open the group in DHIS2 Maintenance and
   assign the new data elements manually.
