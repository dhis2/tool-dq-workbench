Integrity stages
// // ===================================
// Integrity stages can be used to the number of metadata integrity violations for each
metadata integrity check. As an example, for the check called `Category options with no categories`,
we might have 4 errors on a given day. When the integrity stage is run, it will
// summarize the number of errors for each integrity check and store this in a data value in DHIS2.
We can then start to resolve this particular issue by removing the category options
// that have no categories assigned to them. The next day when the integrity stage is run again, the number of errors
// for the `Category options with no categories` check will be 0, indicating that the issue has been resolved.

To define a new integrity stage, press the "DQ monitor" link in the left menu, and then click
"New integrity stage". You will be presented with a form to fill in the details of the integrity stage.
Each of the fields in the form are described below:
- **Monitoring data element group**:
