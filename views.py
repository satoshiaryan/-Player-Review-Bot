    embed.set_footer(
        text=f"Reviewed by {review.get('reviewer_name', 'Unknown')} • ID: {review.get('id', 'N/A')}",
        icon_url="https://cdn.discordapp.com/embed/avatars/0.png"
    )
    
    # Set image - use stored base64 data first (permanent), fallback to URL
    if review.get('image_data'):
        try:
            image_bytes = base64.b64decode(review['image_data'])
            image_file = discord.File(io.BytesIO(image_bytes), filename="card.png")
            embed.set_image(url="attachment://card.png")
            # We need to return the file too - this is handled in the calling function
        except Exception as e:
            print(f"⚠️ Could not decode image: {e}")
            if review.get('image_url'):
                embed.set_image(url=review['image_url'])
    elif review.get('image_url'):
        embed.set_image(url=review['image_url'])
    
    return embed
