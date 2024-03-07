from datetime import datetime, timedelta
from requests import Session

from . import DataFormat
from .auth import Authenticator
from .cache import DataCache
from . import config as mod_config
from .pipeline import Pipeline
from . import query as mod_query
from .telemetry import print_info


CSV_SLICE_SIZE = 1000
SALESFORCE_CREATED_DATE_QUERY = \
    "SELECT Id,EventType,CreatedDate,LogDate,Interval,LogFile,Sequence From EventLogFile Where CreatedDate>={" \
    "from_timestamp} AND CreatedDate<{to_timestamp} AND Interval='{log_interval_type}'"
SALESFORCE_LOG_DATE_QUERY = \
    "SELECT Id,EventType,CreatedDate,LogDate,Interval,LogFile,Sequence From EventLogFile Where LogDate>={" \
    "from_timestamp} AND LogDate<{to_timestamp} AND Interval='{log_interval_type}'"


class SalesForce:
    def __init__(
        self,
        instance_name: str,
        config: mod_config.Config,
        data_cache: DataCache,
        authenticator: Authenticator,
        pipeline: Pipeline,
        initial_delay: int,
        queries=None,
    ):
        self.instance_name = instance_name
        self.default_api_ver = config.get('api_ver', '52.0')
        self.data_cache = data_cache
        self.auth = authenticator
        self.time_lag_minutes = config.get(
            mod_config.CONFIG_TIME_LAG_MINUTES,
            mod_config.DEFAULT_TIME_LAG_MINUTES if not self.data_cache else 0,
        )
        self.date_field = config.get(
            mod_config.CONFIG_DATE_FIELD,
            mod_config.DATE_FIELD_LOG_DATE if not self.data_cache \
                else mod_config.DATE_FIELD_CREATE_DATE,
        )
        self.generation_interval = config.get(
            mod_config.CONFIG_GENERATION_INTERVAL,
            mod_config.DEFAULT_GENERATION_INTERVAL,
        )
        self.last_to_timestamp = (datetime.utcnow() - timedelta(
            minutes=self.time_lag_minutes + initial_delay
        )).isoformat(timespec='milliseconds') + 'Z'

        if queries:
            self.queries = queries
        else:
            self.queries = [{
                'query': SALESFORCE_LOG_DATE_QUERY \
                    if self.date_field.lower() == 'logdate' \
                    else SALESFORCE_CREATED_DATE_QUERY
            }]

        self.pipeline = pipeline

    def authenticate(self, sfdc_session: Session):
        self.auth.authenticate(sfdc_session)

    def slide_time_range(self):
        self.last_to_timestamp = (
            datetime.utcnow() - timedelta(minutes=self.time_lag_minutes)) \
                .isoformat(timespec='milliseconds') + "Z"

    # NOTE: Is it possible that different SF orgs have overlapping IDs? If this is possible, we should use a different
    #       database for each org, or add a prefix to keys to avoid conflicts.

    def fetch_logs(self, session: Session) -> list[dict]:
        print_info(f"Queries = {self.queries}")

        for query in self.queries:
            response = mod_query.New(
                query,
                self.time_lag_minutes,
                self.last_to_timestamp,
                self.generation_interval,
                self.default_api_ver,
            ).execute(
                session,
                self.auth.get_instance_url(),
                self.auth.get_access_token(),
            )

            # Show query response
            #print("Response = ", response)

            self.pipeline.execute(
                session,
                query,
                self.auth.get_instance_url(),
                self.auth.get_access_token(),
                response['records'],
            )

        self.slide_time_range()

# @TODO need to handle this logic but only when exporting logfiles and at this
# level we don't make a distinction but in the pipeline we don't have the right
# info from this level to reauth
#
#    try:
#        download_response = download_file(session, f'{url}{record_file_name}')
#        if download_response is None:
#            return
#    except SalesforceApiException as e:
#        pass
#        if e.err_code == 401:
#            if retry:
#                print_err("invalid token while downloading CSV file, retry auth and download...")
#                self.clear_auth()
#                if self.authenticate(self.oauth_type, session):
#                    return self.build_log_from_logfile(False, session, record, query)
#                else:
#                    return None
#            else:
#                print_err(f'salesforce event log file "{record_file_name}" download failed: {e}')
#                return None
#        else:
#            print_err(f'salesforce event log file "{record_file_name}" download failed: {e}')
#            return None
#    except RequestException as e:
#        print_err(
#            f'salesforce event log file "{record_file_name}" download failed: {e}'
#        )
#        return
#
#    csv_rows = self.parse_csv(download_response, record_id, record_event_type, cached_messages)
#
#    print_info(f"CSV rows = {len(csv_rows)}")
