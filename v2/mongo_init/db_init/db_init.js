use("db")
if (db.getCollectionNames().length !== 0){
  console.log("Database was already initialized!")
  exit(0)
}
db.createCollection('queries')
db.queries.createIndex({"uid": 1})
db.createCollection('users')
db.users.createIndex({"tokens.token": 1})
db.createCollection('taxons')
db.taxons.createIndex({"priority": -1, "name": 1})
console.log("Database initialized!")

// TODO: fill taxon collection? no, better to do find/upsert on load
