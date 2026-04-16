# python script for upcl

this work both with frontend and script 

## Installation

Install my-project with 

git clone https://github.com/NAMANNIMBLE1/upcl_backend_script.git

```bash
install python >= 3.8

python -m venv .venv

source .venv/Script/activate 
for linux source .venv/bin/activate


pip install -r requirements.txt


for frontend 

streamlit run app.py 

for direct script run 

python app.py ( after activating .venv )


```

## Usage/Examples


# for using script directly 

### set dry_run = true / false in sample.py 

### dry run will not execute in db but show the changes 

### setup config = {} inside the sample.py 

## edit raw_tickets = []

  ##### add data here 
  ##### format is -> Ticket(ref, subcategory, category, status, priority,start_date, close_date, ttr_finish_date,division_name, agent_name, ttr_100_passed)


## sample example data 

###### ('I-004325', 'IT Issue \\ Application \\ Billing', 'Applications', 'closed', '4', '2026-03-10 13:50:37', '2026-03-10 14:11:38', '2026-03-09 23:26:11', 'Data_Center', 'ankitp', 1)



# for frontend

##### run streamlit app.py 

###### add teh data in fields and add that ticket ( you can add multiple tickets ) then generate sql and check it & execute it ( no dry run here direct execution permanent )

## License

[MIT](https://choosealicense.com/licenses/mit/)