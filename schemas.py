from pydantic import BaseModel
import datetime as dt


class PaycorResponse(BaseModel):
    status: str
    message: str
    data: dict


class PaycorAccessTokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str


class PaycorAccessTokenRequest(BaseModel):
    refresh_token: str
    client_id: str
    client_secret: str


class PaycorEmployeeResource(BaseModel):
    id: str
    url: str


class PaycorEmployee(BaseModel):
    id: str
    employeeNumber: int
    firstName: str
    middleName: str | None = None
    lastName: str
    employee: PaycorEmployeeResource


class PaycorGetEmployeesResponse(BaseModel):
    hasMoreResults: bool
    continuationToken: str | None = None
    additionalResultsUrl: str | None = None
    records: list[PaycorEmployee]


class PaycorTimeOffRequestDay(BaseModel):
    timeOffRequestDayId: str
    date: dt.date
    hours: float
    startTime: dt.datetime | dt.date | None = None
    endTime: dt.datetime | dt.date | None = None
    isPartial: bool


class PaycorTimeOffRequest(BaseModel):
    legalEntityId: int
    timeOffRequestId: str
    benefitCode: str
    totalHours: float
    days: list[PaycorTimeOffRequestDay]
    comment: str | None = None
    status: str
    createdDate: dt.datetime
    statusUpdateTime: dt.datetime
    statusUpdateByEmployeeId: str
    createdByEmployeeId: str
    employeeId: str
    # Employee name fields (will be populated by hydration)
    employeeFirstName: str | None = None
    employeeLastName: str | None = None
    employeeFullName: str | None = None


class PaycorGetTimeOffRequestsResponse(BaseModel):
    hasMoreResults: bool
    continuationToken: str | None = None
    additionalResultsUrl: str | None = None
    records: list[PaycorTimeOffRequest]
