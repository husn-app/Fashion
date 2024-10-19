### User-facing APIs
## Public - Read only
1. `get_similar_products(product_id)` -> Returns a list of `128` similar products for the product_id. 
2. `search(query)` -> Returns a list of `128` matching products.
3. `get_product(product_id)` -> Returns the product for the product id. 
4. `get_inspirations(gender)` -> Returns inspirations for the given gender. 

## User - Readonly
1. `get_feed(user_id)` -> Returns a list of `128` products that are relevant to the user. Each product also has is_wishlisted attribute. 
2. `get_wishlisted_products(user_id)` -> Returns a list of `128` user's wishlisted products sorted by time desc.

## User - Interactions
1. `toggle_product_wishlist_status(user_id, product_id)` : toggles the status of product_id's wishlist status and returns {'wishlist_status' : True/False}

## User - Auth : TODO
1. `add_user_to_db(auth_id, email, name, given_name, family_name, picture_url)` : Adds user to db.
2. `get_user(user_id, user_email)` : Returns user obj. 
3. `onboarding` : TODO

## Logging & Analytics. 
1. `log_search(user_id, session_id, clicked_object_info, query)` - Log which user and session searched for what. clicked_object_info could be inspirations or something written somewhere. 
2. `log_product_click(user_id, session_id, clicked_obj_info, product_id)` : Log user's product_click. clicked_obj_info could be `inspiration/<subcategory>/<category>`


## Session storage
1. User comes to the website for the first time - Add session_id. 
2. User logs in for the first time - 


### Myntra Image Loading
1. Loads the image on the products page using `/f_webp,dpr_2.0,q_60,w_210,c_limit,fl_progressive/assets`
    - f_webp,q_60 means there's lossy webp compression. q_100 takes 81 KB, q_95 50KB, q_80 18KB, q_60 takes 12KB. Default is q_80
    - without f_webp,q_60 takes 30s. without f_webp, for the same q_* the size is higher, for example q_60 is 20KB, q_80 is 30KB. so it's probably using some other compression method as default. 
2. Loads the image on single product page using `/h_720,q_90,w_540`.
    - doesn't use f_webp somehow even thouogh it's smaller and difference is not noticeable. 


Notes from TODO:
Currently, the search image seem to be all 3:4, 1440x1080px.
They're rendered on (Pixel7) as 199x265 px. Myntra allows newer api to retrive iamges:
https://assets.myntassets.com/h_1080,q_80,w_1440/v1/assets/images/* where h_ , w_, q_ can be replaced.
I saw that at lower values download timing is neglible <= 1ms, but server time increases, maybe because 
they're cropping the image at run-time for non-conventional sizes. Surprisingly even at 1440x1080px,
the download speed is quite good at ~15ms on my laptop. Take a decision later on calling smaller
sizes of assets or not, for low bandwidth.


### Retrieval Models
1. Retrieval results for some of the famous models including SigLiP are in [open_clip/openclip_retrieval_results](https://github.com/mlfoundations/open_clip/blob/main/docs/openclip_retrieval_results.csv), sorted results are in this [doc](https://docs.google.com/spreadsheets/d/1ilPJexX2m03QtX74iaeGCdBQ3sVm5jYqQ0Kv2BgrDe0/edit?gid=1066211703#gid=1066211703)
2. There are two heads one for image and one for text. We can load only the text module for now.
3. There's a much smaller mobile-clip variant from apple : https://github.com/apple/ml-mobileclip
4. This [tweet](https://x.com/giffmana/status/1717999891937394990) from Lucas says there is a 87M clip as well, which performs exceptionally, but I haven't found this variant anywhere.
5. Note that we also need to optimize for number of dimensions in the output, since that will take up latency during retrieval. The current Vit-B-32 has 512 dimensions, but some siglip variants have higher like 768. 
