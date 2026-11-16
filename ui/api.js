"use strict";

// JSON transport and recorder errors. Application state stays with the caller.
globalThis.SaigenAPI=Object.freeze({create(getToken){
return async function request(path,body){
 const response=await fetch(path,{method:body?"POST":"GET",headers:body?{"Content-Type":"application/json","X-Saigen-Token":getToken()}:{},body:body?JSON.stringify(body):undefined});
 let value;try{value=await response.json();}catch{throw new Error("The local recorder returned an invalid response.");}
 if(!response.ok){const error=new Error(value.error||"The request failed.");error.status=response.status;throw error;}
 return value;
}
}});
