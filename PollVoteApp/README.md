The application and the documentation have been written by Leonardo Consoli for the Assignment: Build Something of the course PA2577 HT26 lp1 E2546 Applied Cloud Computing and Big Data

# Poll & Vote App
PollVoteApp is an application created to imitate the 2026 Swedish general election that happened during the first weeks of September. It enables users to create and vote for polls in real time with its microservice architecture, containerized with Docker and orchestrated by Kubernetes. 
For this application I chose to use FastAPI because it’s one of the fastest frameworks for python and it’s ideal for microservices where the management of the voting requests and authentication requires minimum response time. Also, the microservices written with FastAPI utilize stateless JWT tokens so the containers remain independent and immediately horizontally scalable on Kubernetes. 

## Architecture
The application is divided into in the following independent components:
-	Auth Service (`Containers/AuthService`):
Handles the registration and the login of the user. Saves the cyphered passwords with Bcrypt on MongoDB and generates the JSON Web Tokens. Thanks to the stateless authentication it remains scalable horizontally. The port for this microservice is the 8003.

-	 Vote Service (`Containers/VoteService`):
Handles the polls votes, also verifies on MongoDB if the user has already voted to that specific poll. The port for this microservice is the 8002.

-	Frontend (`Containers/Frontend`)
Serviced static application serviced with Nginx (internal port 80 exposed on 9090). It’s composed of the login, registration, creation of the polls and voting parts. Also shows the status of the different polls votes to the user.

-	Database (‘MongoDB’)
NoSQL database on the port 27017 with PersistentVolumeClaim (‘mongo-pvc’) to grant the persistence of the data even after the restart of the container/pod. I’ve decided to use MongoDB because of the hierarchical structure of the voting database (a poll contains a list of options and the respective votes and a list of the users voting). It’s also simple to update directly with operators such has ‘$inc’ for the votes or ‘$push’ to add another user to the voting list. It’s also possible to create automatic queries like `voted_by: {"$ne": user}`that prevents the double votes for a user. 

## How to Deploy
To compile the project and execute it on any machines are necessary the following components: 
Docker, a Kubernetes cluster active and kubectl configure to interact with the cluster.
--- Instructions to Build and Push: 
position yourself in the PollVoteApp main folder and execute the following commands (note that the examples are with bash). 

Step 1: Run the Setup Script
Navigate to the root folder of the project in your terminal and run:

```bash
# Universal command (runs on Linux, macOS, and Windows without requiring any permission changes):
bash setup.sh

# Optional: rebuild images locally before deploying
bash setup.sh --build
```
*(If the repository was cloned via Git, `./setup.sh` also works directly).*


Step 2: Verify the pods (check if all are in the running state):

kubectl get pods


Step 3: Access the application:
Open your browser at `http://localhost:9090`

## Scalability Notes 
As asked by the requirements for the project all the microservices can scale horizontally and independently without causing the interruption of the service. In a possible scenario in which the application is open to the public and used by many users then there would be many thousands of votes being sent in a short time span. This would cause more writing on the database than reading, but thanks to the containerization and to FastAPI the application can scale without trouble.  Kubernetes automatically distributes incoming requests across all replicas of vote-deployment via the Service's internal load balancing, regardless of the Service type used for external exposure. Another solution would be to use the ‘Sharding’ technique on the MongoDB to create replica sets.
e.g. ‘kubectl scale deployment vote-deployment --replicas=3’

## Known Limitations
The known limitations of the current application are:
-Single instance database: even though there is PVC on MongoDB the absence of a cluster ReplicaSet or a Sharded means that the database doesn’t offer high availability nor horizontal database scalability.
-Parallel writing on the Database: In the project a message queue is not implemented, so extremely high concurrent write frequency on the same specific poll document could create contention, even though MongoDB's atomic $inc operator prevents data corruption.
-Secret management: the JWT ciphered is defined clearly in the deployment.yaml manifest, it should be managed with Kubernetes secrets or other services.
