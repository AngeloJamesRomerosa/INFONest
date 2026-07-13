import streamlit as st
from transformers.models.bart import BartForConditionalGeneration, BartTokenizer
from transformers import GenerationConfig 
import os

@st.cache_resource
def load_bart_model():
    model = BartForConditionalGeneration.from_pretrained(
        "sshleifer/distilbart-cnn-12-6",
        use_safetensors=False
    ).to("cpu")
    return model

@st.cache_resource
def load_bart_tokenizer():
    tokenizer = BartTokenizer.from_pretrained(
        "sshleifer/distilbart-cnn-12-6"
    )
    return tokenizer

#import streamlit as st
#from transformers.models.bart import BartForConditionalGeneration, BartTokenizer
#from transformers import GenerationConfig 
#import os

#@st.cache_resource
#def load_bart_model():
    #token = os.getenv("HF_TOKEN")
    #model = BartForConditionalGeneration.from_pretrained(
        #"sshleifer/distilbart-cnn-12-6",
        #"Angel0J/distilbart-multi_news-12-6_2",
        #use_safetensors=False,
        #use_auth_token=token
    #).to("cpu")
    #model.generation_config = GenerationConfig.from_model_config(model.config)
    #model.generation_config.early_stopping = False  # Set to False to avoid the validation error
    #return model
    # Explicitly set the GenerationConfig with a valid early_stopping value
    

#@st.cache_resource
#def load_bart_tokenizer():
    #token = os.getenv("HF_TOKEN")
    #tokenizer = BartTokenizer.from_pretrained(
        #"sshleifer/distilbart-cnn-12-6",
        #"Angel0J/distilbart-multi_news-12-6_2",
        #use_auth_token=token
    #)
    #return tokenizer






#ORIGINAL CODE:

#import streamlit as st
#from transformers import BartForConditionalGeneration, BartTokenizer
#from transformers.models.bart import BartForConditionalGeneration, BartTokenizer

#@st.cache_resource
#def load_bart_model():
    #model = BartForConditionalGeneration.from_pretrained("sshleifer/distilbart-cnn-12-6", use_safetensors=False).to("cpu")
    #return model
#@st.cache_resource
#def load_bart_tokenizer():
    #tokenizer = BartTokenizer.from_pretrained("sshleifer/distilbart-cnn-12-6")
    #return tokenizer