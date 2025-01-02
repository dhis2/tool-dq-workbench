import datetime
import re
from datetime import datetime
from dateutil.relativedelta import relativedelta

class Dhis2PeriodUtils:
    @staticmethod
    def previous_monthly_periods(period, number_of_periods):
        date = datetime.strptime(period, "%Y%m")
        previous_periods = [date - relativedelta(months=i) for i in range(1, number_of_periods + 1)]
        return {p.strftime("%Y%m") for p in previous_periods}

    @staticmethod
    def previous_weekly_periods(period, number_of_periods):
        year, week = int(period[:4]), int(period[5:])
        date = datetime.strptime(f'{year}-W{week}-1', "%Y-W%W-%w")
        previous_periods = [date - relativedelta(weeks=i) for i in range(1, number_of_periods + 1)]
        return {f"{p.isocalendar()[0]}W{p.isocalendar()[1]:02d}" for p in previous_periods}

    @staticmethod
    def previous_daily_periods(period, number_of_periods):
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
    def current_monthly_period(date):
        date = datetime.strptime(date, "%Y-%m-%d")
        return date.strftime("%Y%m")

    @staticmethod
    def current_weekly_period(date):
        date = datetime.strptime(date, "%Y-%m-%d")
        return date.strftime("%GW%V")

    @staticmethod
    def current_daily_period(date):
        date = datetime.strptime(date, "%Y-%m-%d")
        return date.strftime("%Y%m%d")

    @staticmethod
    def current_quarterly_period(date=None):
        date = datetime.strptime(date, "%Y-%m-%d")
        quarter = (date.month - 1) // 3 + 1
        return f"{date.year}Q{quarter}"

    def get_current_period(self, date=None, period_type='Monthly'):
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        else:
            date_format = re.compile(r'\d{4}-\d{2}-\d{2}')
            if not date_format.match(date):
                raise ValueError("Date format is not correct")

        if period_type == 'Monthly':
            return self.current_monthly_period(date)
        elif period_type == 'Weekly':
            return self.current_weekly_period(date)
        elif period_type == 'Daily':
            return self.current_daily_period(date)
        elif period_type == 'Quarterly':
            return self.current_quarterly_period(date)
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
        else:
            raise ValueError("Unsupported period type")

    @staticmethod
    def get_start_date_from_today(duration_string):
        amount, unit = duration_string.split(' ')
        amount = int(amount)

        if amount is None or len(unit) == 0:
            raise ValueError("Invalid duration format")

        unit = unit.rstrip('s')
        supported_units = {'day': 'days', 'week': 'weeks', 'month': 'months', 'year': 'years'}

        if unit not in supported_units:
            raise ValueError("Invalid duration unit")

        delta = relativedelta(**{supported_units[unit]: amount})
        return datetime.now() - delta