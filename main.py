import httpx
import datetime as dt
import json
from jinja2 import Environment, FileSystemLoader
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from schemas import (
    PaycorAccessTokenResponse,
    PaycorAccessTokenRequest,
    PaycorGetEmployeesResponse,
    PaycorGetTimeOffRequestsResponse,
)
from dotenv import dotenv_values

config = dotenv_values(".env")


def get_access_token(refresh_token):
    url = "https://apis.paycor.com/v1/authenticationsupport/retrieveAccessTokenWithRefreshToken"
    headers = {"Ocp-Apim-Subscription-Key": "4fb31e53f68d46f685ef12514d2562bf"}
    data = PaycorAccessTokenRequest(
        refresh_token=refresh_token,
        client_id="58c4d3f65726e2c3bbf6",
        client_secret="ZCIU39gjH4Sx039t3cPcAgfVuClk1RM1Jmu1jW14Q4",
    )
    response = httpx.post(url, headers=headers, json=data.model_dump())
    response.raise_for_status()
    return PaycorAccessTokenResponse(**response.json())


def get_employees(access_token):
    url = "https://apis.paycor.com/v1/tenants/226986/employees?statusFilter=Active"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Ocp-Apim-Subscription-Key": "4fb31e53f68d46f685ef12514d2562bf",
    }
    response = httpx.get(url, headers=headers)
    return PaycorGetEmployeesResponse(**response.json())


def get_all_employees(access_token):
    """Get all employees and create a lookup dictionary by employee ID"""
    employees_response = get_employees(access_token)
    employee_lookup = {}

    for employee in employees_response.records:
        employee_lookup[employee.id] = {
            "firstName": employee.firstName,
            "lastName": employee.lastName,
            "fullName": f"{employee.firstName} {employee.lastName}".strip(),
        }

    return employee_lookup


def get_time_off_requests(access_token, employee_lookup=None):
    # Get today's ISO date for filtering
    today = dt.date.today()
    today_iso = today.isoformat()

    url = f"https://apis.paycor.com/v1/legalentities/190559/timeoffrequests?startDate={today_iso}&endDate={today_iso}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Ocp-Apim-Subscription-Key": "4fb31e53f68d46f685ef12514d2562bf",
    }
    response = httpx.get(url, headers=headers)
    time_off_response = PaycorGetTimeOffRequestsResponse(**response.json())

    # Hydrate with employee names if lookup is provided
    if employee_lookup:
        for request in time_off_response.records:
            employee_data = employee_lookup.get(request.employeeId)
            if employee_data:
                request.employeeFirstName = employee_data["firstName"]
                request.employeeLastName = employee_data["lastName"]
                request.employeeFullName = employee_data["fullName"]

    return time_off_response


def save_time_off_data_to_json(requests, filename="time_off_data.json"):
    """Save time off requests to a JSON file for the HTML table to read"""
    data = []
    for request in requests:
        # Convert datetime objects to strings for JSON serialization
        request_data = {
            "employeeFullName": request.employeeFullName,
            "benefitCode": request.benefitCode,
            "totalHours": request.totalHours,
            "status": request.status,
            "comment": request.comment,
            "days": [],
        }

        for day in request.days:
            day_data = {
                "date": day.date.isoformat() if day.date else None,
                "hours": day.hours,
                "startTime": day.startTime.isoformat() if day.startTime else None,
                "endTime": day.endTime.isoformat() if day.endTime else None,
                "isPartial": day.isPartial,
            }
            request_data["days"].append(day_data)

        data.append(request_data)

    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Time off data saved to {filename}")


def prepare_requests_for_template(requests):
    """Prepare request data for Jinja2 template rendering"""
    template_data = []

    for request in requests:
        # Get the first day's start and end times
        first_day = request.days[0] if request.days else None

        if first_day and first_day.startTime and first_day.endTime:
            start_time_obj = first_day.startTime
            end_time_obj = first_day.endTime

            # Check if it's an all-day request (00:00 to 23:59)
            if start_time_obj.time() == dt.time(
                0, 0
            ) and end_time_obj.time() == dt.time(23, 59):
                start_time = "All Day"
                end_time = ""
            else:
                # Show just the time part
                start_time = start_time_obj.strftime("%H:%M")
                end_time = end_time_obj.strftime("%H:%M")
        else:
            start_time = "N/A"
            end_time = "N/A"

        template_data.append(
            {
                "employeeFullName": request.employeeFullName or "Unknown",
                "benefitCode": request.benefitCode,
                "start_time": start_time,
                "end_time": end_time,
                "status": request.status,
                "totalHours": request.totalHours,
            }
        )

    return template_data


def generate_html_with_jinja2(requests, filename="time_off_table.html"):
    """Generate HTML using Jinja2 template"""
    # Ensure templates directory exists
    os.makedirs("templates", exist_ok=True)

    # Set up Jinja2 environment
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("time_off_table.html")

    # Prepare data for template
    template_data = prepare_requests_for_template(requests)

    html_content = template.render(requests=template_data)

    # Write to file
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"HTML table generated with Jinja2 and saved to {filename}")


def generate_email_safe_html(requests, filename="time_off_email.html", save_html=False):
    """Generate email-safe HTML with inline styles"""
    # Ensure templates directory exists
    os.makedirs("templates", exist_ok=True)

    # Set up Jinja2 environment
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("time_off_email.html")

    # Prepare data for template
    template_data = prepare_requests_for_template(requests)

    def get_ordinal(n):
        if 10 <= n % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return str(n) + suffix

    today = dt.datetime.today()
    formatted_today = (
        today.strftime("%B") + " " + get_ordinal(today.day) + ", " + str(today.year)
    )

    # Render template
    html_content = template.render(
        requests=template_data, formatted_today=formatted_today
    )

    # Write to file
    if save_html:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)

    # print(f"Email-safe HTML generated and saved to {filename}")
    return html_content


def send_email(
    html_content,
    sender_email,
    recipient_emails,
):
    # Create date-based subject
    today = dt.date.today()
    subject = f"Daily Time Off - {today.strftime('%b')} {today.day}, {today.year}"

    try:
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = ", ".join(recipient_emails)

        # Attach HTML content
        html_part = MIMEText(html_content, "html")
        msg.attach(html_part)

        # Connect to server and send email
        with smtplib.SMTP(config["SMTP_SERVER"], config["SMTP_PORT"]) as server:
            server.starttls()  # Enable TLS encryption
            server.login(config["SMTP_USERNAME"], config["SMTP_PASSWORD"])
            server.sendmail(sender_email, recipient_emails, msg.as_string())

        print(
            f"Email sent successfully to {', '.join(recipient_emails)}, Subject: {subject}"
        )
        return True

    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False


def main():
    with open("access_tokens.json", "r") as f:
        access_tokens = PaycorAccessTokenResponse(**json.load(f))

    old_refresh_token = access_tokens.refresh_token

    refresh_response = get_access_token(old_refresh_token)

    with open("access_tokens.json", "w") as f:
        json.dump(refresh_response.model_dump(), f, indent=4)

    access_token = refresh_response.access_token

    # Get employee lookup for hydration
    employee_lookup = get_all_employees(access_token)

    # Get time off requests with employee names
    time_off_requests = get_time_off_requests(access_token, employee_lookup)

    # Filter to only "Approved" requests
    approved_requests = [
        request for request in time_off_requests.records if request.status == "Approved"
    ]

    # Update benefitCode: change "Sick" to "PTO"
    for request in approved_requests:
        if request.benefitCode != "WFH":
            request.benefitCode = "PTO"

    # Sort approved requests by benefit code descending
    approved_requests.sort(key=lambda request: request.benefitCode or "", reverse=True)

    # Print approved requests data
    # print(f"Found {len(time_off_requests.records)} total time off requests")
    # print(f"Found {len(approved_requests)} approved time off requests")
    # print("\n=== APPROVED TIME OFF REQUESTS ===")
    # for request in approved_requests:
    #     print(
    #         f"Employee: {request.employeeFullName or 'Unknown'} ({request.employeeId})"
    #     )
    #     print(f"Status: {request.status}, Hours: {request.totalHours}")
    #     print(f"Comment: {request.comment or 'No comment'}")
    #     print("---")

    # Save data to JSON file for the HTML table
    # save_time_off_data_to_json(approved_requests)

    # Generate HTML table using Jinja2
    # generate_html_with_jinja2(approved_requests)

    # Generate email-safe HTML
    email_html = generate_email_safe_html(approved_requests, save_html=False)

    # Send email with the HTML content
    # Configure your email settings here
    sender_email = config["EMAIL_FROM"]
    recipient_emails = [config["EMAIL_TO"]]

    # Send the email with the HTML content
    send_email(
        email_html,
        sender_email=sender_email,
        recipient_emails=recipient_emails,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        send_email(
            html_content=f"An error occurred: {str(e)}",
            sender_email="bfisher@tbgfs.com",
            recipient_emails=["bfisher@tbgfs.com"],
        )
