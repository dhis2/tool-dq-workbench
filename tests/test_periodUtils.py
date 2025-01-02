import unittest
import sys
import os
from lib.periodUtils import Dhis2PeriodUtils

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestDhis2PeriodUtils(unittest.TestCase):

    def test_previous_monthly_periods(self):
        result = Dhis2PeriodUtils.previous_monthly_periods("202301", 3)
        self.assertSetEqual(result, {"202212", "202211", "202210"})

    def test_previous_weekly_periods(self):
        result = Dhis2PeriodUtils.previous_weekly_periods("2023W01", 3)
        self.assertSetEqual(result, {"2022W52", "2022W51", "2022W50"})

    def test_previous_daily_periods(self):
        result = Dhis2PeriodUtils.previous_daily_periods("20230101", 3)
        self.assertSetEqual(result, {"20221231", "20221230", "20221229"})

    def test_previous_quarterly_periods(self):
        result = Dhis2PeriodUtils.previous_quarterly_periods("2023Q1", 3)
        self.assertSetEqual(result, {"2022Q4", "2022Q3", "2022Q2"})

    def test_get_previous_periods(self):
        dhis2_period_utils = Dhis2PeriodUtils()
        result = dhis2_period_utils.get_previous_periods("202301", "Monthly", 3)
        self.assertSetEqual(result, {"202212", "202211", "202210"})

        result = dhis2_period_utils.get_previous_periods("2023W01", "Weekly", 3)
        self.assertSetEqual(result, {"2022W52", "2022W51", "2022W50"})

        result = dhis2_period_utils.get_previous_periods("20230101", "Daily", 3)
        self.assertSetEqual(result, {"20221231", "20221230", "20221229"})

        result = dhis2_period_utils.get_previous_periods("2023Q1", "Quarterly", 3)
        self.assertSetEqual(result, {"2022Q4", "2022Q3", "2022Q2"})

    def test_unsupported_period_type(self):
        dhis2_period_utils = Dhis2PeriodUtils()
        with self.assertRaises(ValueError):
            dhis2_period_utils.get_previous_periods("202301", "Unsupported", 3)

    def test_current_monthly_period(self):
        date = "2023-01-01"
        result = Dhis2PeriodUtils.current_monthly_period(date)
        self.assertEqual(result, "202301")

    def test_current_weekly_period(self):
        date = "2023-01-01"
        result = Dhis2PeriodUtils.current_weekly_period(date)
        self.assertEqual(result, "2022W52")

    def test_current_daily_period(self):
        date = "2023-01-01"
        result = Dhis2PeriodUtils.current_daily_period(date)
        self.assertEqual(result, "20230101")

    def test_current_quarterly_period(self):
        date = "2023-01-01"
        result = Dhis2PeriodUtils.current_quarterly_period(date)
        self.assertEqual(result, "2023Q1")

    def test_current_period(self):
        dhis2_period_utils = Dhis2PeriodUtils()
        date = "2023-01-01"
        result = dhis2_period_utils.get_current_period(date, "Monthly")
        self.assertEqual(result, "202301")

        result = dhis2_period_utils.get_current_period(date, "Weekly")
        self.assertEqual(result, "2022W52")

        result = dhis2_period_utils.get_current_period(date, "Daily")
        self.assertEqual(result, "20230101")

        result = dhis2_period_utils.get_current_period(date, "Quarterly")
        self.assertEqual(result, "2023Q1")


if __name__ == "__main__":
    unittest.main()
