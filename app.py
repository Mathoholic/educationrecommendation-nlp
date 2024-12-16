from flask import Flask, request, jsonify, render_template
from chromadb import PersistentClient
from sentence_transformers import SentenceTransformer
import json
import re
import logging
from pymongo import MongoClient
from dataclasses import dataclass
from typing import Optional, List, Dict
import os
from dotenv import load_dotenv
from bson.json_util import dumps

# Load environment variables
load_dotenv()

# ChromaDB for vector search
chroma_client = PersistentClient("./dataembeds")
collection = chroma_client.get_or_create_collection("embeddings_programs")

# MongoDB for program details
mongo_client = MongoClient(os.getenv('qastring'))
db = mongo_client['visionway-prodapsouth1-b2bandb2c']
programs_collection = db['search_program']

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize ChromaDB and model
chroma_client = PersistentClient("./dataembeds")
collection = chroma_client.get_or_create_collection("embeddings_programs")
model = SentenceTransformer('all-MiniLM-L6-v2')

@dataclass
class ProgramResult:
    program_id: str
    name: str
    description: str
    requirements: str
    campus_location: str
    institution: str
    similarity: float = 0.0

@dataclass
class ProgramModel:
    program_id: str
    program_name: str
    program_description: str
    institution_name: str
    campus_location: str
    discipline: str
    program_level: str
    tuition_fees: float
    currency: str
    program_length: int
    program_intakes: List[Dict]
    requirements: Optional[str] = None
    similarity_score: float = 0.0

def load_data():
    try:
        collection = chroma_client.get_or_create_collection("embeddings_programs")
        
        # Check if collection is empty
        if collection.count() == 0:
            with open('data.json', 'r') as f:
                programs = json.load(f)
            
            # Prepare data for ChromaDB
            documents = [str(prog) for prog in programs]
            embeddings = model.encode(documents).tolist()
            ids = [str(i) for i in range(len(programs))]
            
            # Add to collection
            collection.add(
                embeddings=embeddings,
                documents=documents,
                ids=ids,
                metadatas=programs
            )
            app.logger.info(f"Loaded {len(programs)} programs into ChromaDB")
        return collection
    except Exception as e:
        app.logger.error(f"Error loading data: {str(e)}")
        raise

def fetch_all_metadata():
    print("Fetching all metadata from ChromaDB...")
    all_metadatas = []
    offset = 0
    batch_size = 100
    has_more = True

    try:
        while has_more:
            data = collection.get(limit=batch_size, offset=offset)
            
            # Extract metadata from batch
            if data and data['metadatas']:
                all_metadatas.extend(data['metadatas'])
                offset += batch_size
                print(f"Fetched {len(all_metadatas)} records so far...")
            else:
                has_more = False
                
            # Optional: Print combined text content
            if data and data.get('documents'):
                print("\nCombined text content:")
                for doc in data['documents']:
                    print(f"- {doc[:100]}...") # Print first 100 chars
                    
    except Exception as e:
        print(f"Error fetching metadata: {str(e)}")
        return []
        
    print(f"\nCompleted fetching {len(all_metadatas)} total records")
    return all_metadatas

def fetch_all_program_ids():
    """Fetch all program IDs from ChromaDB."""
    program_ids = []
    offset = 0
    batch_size = 100
    has_more = True

    try:
        while has_more:
            data = collection.get(limit=batch_size, offset=offset)
            
            if data and data['metadatas']:
                # Extract only programId from each metadata record
                batch_ids = [meta.get('programId') for meta in data['metadatas'] if meta.get('programId')]
                program_ids.extend(batch_ids)
                offset += batch_size
                print(f"Fetched {len(program_ids)} program IDs so far...")
            else:
                has_more = False

        print(f"Total program IDs fetched: {len(program_ids)}")
        return program_ids

    except Exception as e:
        app.logger.error(f"Error fetching program IDs: {str(e)}")
        return []

def get_programs_by_ids(program_ids: List[str]) -> Dict[str, dict]:
    """Fetch programs from MongoDB using program IDs"""
    try:
        programs = programs_collection.find({"programId": {"$in": program_ids}})
        return {prog["programId"]: prog for prog in programs}
    except Exception as e:
        app.logger.error(f"MongoDB lookup error: {str(e)}")
        return {}

def search_programs(query: str) -> List[ProgramModel]:
    # 1. Get vector embedding
    query_embedding = model.encode(query).tolist()
    
    # 2. Search ChromaDB
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=10,
        include=["metadatas", "distances"]
    )
    
    # 3. Get MongoDB programs
    program_ids = [meta.get('programId') for meta in results['metadatas'][0]]
    mongo_programs = programs_collection.find({"programId": {"$in": program_ids}})
    
    # 4. Process results
    programs = []
    for program, distance in zip(mongo_programs, results['distances'][0]):
        programs.append(ProgramModel(
            program_id=program.get("programId"),
            program_name=program.get("programName"),
            program_description=program.get("programDescription"),
            institution_name=program.get("institutionName"),
            campus_location=program.get("campusLocation"),
            discipline=program.get("discipline"),
            program_level=program.get("programLevel"),
            tuition_fees=program.get("tutionFees"),
            currency=program.get("currency"),
            program_length=program.get("programLength"),
            program_intakes=program.get("programIntakes"),
            requirements=program.get("additionalRequirements"),
            similarity_score=1 - distance
        ))
    
    return sorted(programs, key=lambda x: x.similarity_score, reverse=True)

# Initialize collection
try:
    collection = load_data()
except Exception as e:
    app.logger.error(f"Failed to initialize collection: {str(e)}")
    raise

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    query = request.form.get('query')
    if not query:
        return jsonify({'error': 'No query provided'}), 400

    try:
        results = search_programs(query)
        return jsonify({
            'results': [program.__dict__ for program in results]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
