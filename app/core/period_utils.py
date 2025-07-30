import datetime
import re
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta

class Dhis2PeriodUtils:
    @staticmethod
    def previous_monthly_periods(period, number_of_periods) -> set:
        date = datetime.strptime(period, "%Y%m")
        previous_periods = [date - relativedelta(months=i) for i in range(1, number_of_periods + 1)]
        return {p.strftime("%Y%m") for p in previous_periods}

    @staticmethod
    def previous_weekly_periods(period, number_of_periods) -> set:
        year, week = int(period[:4]), int(period[5:])
        date = datetime.strptime(f'{year}-W{week}-1', "%Y-W%W-%w")
        previous_periods = [date - relativedelta(weeks=i) for i in range(1, number_of_periods + 1)]
        return {f"{p.isocalendar()[0]}W{p.isocalendar()[1]:02d}" for p in previous_periods}

    @staticmethod
    def previous_daily_periods(period, number_of_periods) -> set:
        date = datetime.strptime(period, "%Y%m%d")
        previous_periods = [date - relativedelta(days=i) for i in range(1, number_of_periods + 1)]
        return {p.strftime("%Y%m%d") for p in previous_periods}

    @staticmethod
    def previous_quarterly_periods(period, number_of_periods):
        year, quarter = int(period[:4]), int(period[5])
        date = datetime(year, (quarter - 1) * 3 + 1, 1)
        previous_periods = [date - relativedelta(months=i*3) for i in range(1, number_of_periods + 1)]
        return {f"{p.year}Q{((p.month - 1) // 3) + 1}" for p in previous_periods}

    @staticmethod
    def previous_yearly_periods(period, number_of_periods):
        year = int(period[:4])
        previous_periods = [year - i for i in range(1, number_of_periods + 1)]
        return {str(y) for y in previous_periods}

    @staticmethod
    def current_monthly_period(date=None):
        if date is None:
            date = datetime.now()
        elif isinstance(date, str):
            date = datetime.strptime(date, "%Y-%m-%d")
        return date.strftime("%Y%m")

    @staticmethod
    def current_weekly_period(date=None):
        if date is None:
            date = datetime.now()
        elif isinstance(date, str):
            date = datetime.strptime(date, "%Y-%m-%d")
        return date.strftime("%GW%V")

    @staticmethod
    def current_daily_period(date=None):
        if date is None:
            date = datetime.now()
        elif isinstance(date, str):
            date = datetime.strptime(date, "%Y-%m-%d")
        return date.strftime("%Y%m%d")

    @staticmethod
    def current_quarterly_period(date=None):
        if date is None:
            date = datetime.now()
        elif isinstance(date, str):
            date = datetime.strptime(date, "%Y-%m-%d")
        quarter = (date.month - 1) // 3 + 1
        return f"{date.year}Q{quarter}"

    @staticmethod
    def current_yearly_period(date=None):
        if date is None:
            date = datetime.now()
        elif isinstance(date, str):
            date = datetime.strptime(date, "%Y-%m-%d")
        return date.strftime("%Y")

    def get_current_period(self, period_type, date=None):
        if date is None:
            date = datetime.now()
        elif isinstance(date, str):
            date = datetime.strptime(date, "%Y-%m-%d")

        if period_type == 'Monthly':
            return self.current_monthly_period(date)
        elif period_type == 'Weekly':
            return self.current_weekly_period(date)
        elif period_type == 'Daily':
            return self.current_daily_period(date)
        elif period_type == 'Quarterly':
            return self.current_quarterly_period(date)
        elif period_type == 'Yearly':
            return self.current_yearly_period(date)
        else:
            raise ValueError("Unsupported period type")


    def get_previous_periods(self, period, period_type, number_of_periods):
        if period_type == 'Monthly':
            return self.previous_monthly_periods(period, number_of_periods)
        elif period_type == 'Weekly':
            return self.previous_weekly_periods(period, number_of_periods)
        elif period_type == 'Daily':
            return self.previous_daily_periods(period, number_of_periods)
        elif period_type == 'Quarterly':
            return self.previous_quarterly_periods(period, number_of_periods)
        elif period_type == 'Yearly':
            return self.previous_yearly_periods(period, number_of_periods)
        else:
            raise ValueError("Unsupported period type")

    @staticmethod
    def get_start_date_from_today(duration_string):
        amount, unit = duration_string.split(' ')
        amount = int(amount)
        unit = unit.rstrip('s')
        supported_units = {'day': 'days', 'week': 'weeks', 'month': 'months', 'year': 'years'}

        if unit not in supported_units:
            raise ValueError(f"Invalid duration unit: {unit}")

        delta = relativedelta(**{supported_units[unit]: amount})
        return datetime.now() - delta

    @staticmethod
    def get_period_type_from_string(period):
        monthly_regex = r'^\d{6}$'
        weekly_regex = r'^\d{4}W\d{2}$'
        daily_regex = r'^\d{8}$'
        quarterly_regex = r'^\d{4}Q\d$'
        yearly_regex = r'^\d{4}$'
        if re.match(monthly_regex, period):
            return 'Monthly'
        elif re.match(weekly_regex, period):
            return 'Weekly'
        elif re.match(daily_regex, period):
            return 'Daily'
        elif re.match(quarterly_regex, period):
            return 'Quarterly'
        elif re.match(yearly_regex, period):
            return 'Yearly'
        else:
            raise ValueError("Unsupported period format")



    def get_start_date_from_period(self, period):
        period_type = self.get_period_type_from_string(period)
        if period_type == 'Monthly':
            return datetime.strptime(period, "%Y%m")
        elif period_type == 'Weekly':
            year, week = int(period[:4]), int(period[5:])
            return datetime.fromisocalendar(year, week, 1)
        elif period_type == 'Daily':
            return datetime.strptime(period, "%Y%m%d")
        elif period_type == 'Quarterly':
            year, quarter = int(period[:4]), int(period[5])
            month = (quarter - 1) * 3 + 1
            return datetime(year, month, 1)
        elif period_type == 'Yearly':
            year = int(period[:4])
            return datetime(year, 1, 1)
        else:
            raise ValueError("Unsupported period type")

    def get_end_date_from_period(self, period):
        period_type = self.get_period_type_from_string(period)
        start_date = self.get_start_date_from_period(period)

        if period_type == 'Monthly':
            return start_date + relativedelta(months=1) - relativedelta(seconds=1)
        elif period_type == 'Weekly':
            return start_date + relativedelta(weeks=1) - relativedelta(seconds=1)
        elif period_type == 'Daily':
            return start_date
        elif period_type == 'Quarterly':
            return start_date + relativedelta(months=3) - relativedelta(seconds=1)
        elif period_type == 'Yearly':
            return start_date + relativedelta(years=1) - relativedelta(seconds=1)
        else:
            raise ValueError("Unsupported period type")
