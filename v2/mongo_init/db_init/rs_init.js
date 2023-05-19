const config = {
  "_id": "rs0",
  "version": 1,
  "members": [
      {
          "_id": 1,
          "host": "mongo:27017"
      },
  ]
};

try {
  if (rs.initiate(config).ok !== 1){
    exit(1)
  }
  console.log("Replica set initialized")
} catch (error) {
  if (error.codeName !== "AlreadyInitialized"){
    throw error;
  }
  console.log("Replica set was already initialized")
}