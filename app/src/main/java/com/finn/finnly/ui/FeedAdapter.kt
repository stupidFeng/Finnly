package com.finn.finnly.ui

import android.content.Intent
import android.net.Uri
import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.finn.finnly.data.model.FeedItem
import com.finn.finnly.databinding.ItemFeedBinding

class FeedAdapter : ListAdapter<FeedItem, FeedAdapter.VH>(DIFF) {

    companion object {
        val DIFF = object : DiffUtil.ItemCallback<FeedItem>() {
            override fun areItemsTheSame(a: FeedItem, b: FeedItem) = a.id == b.id
            override fun areContentsTheSame(a: FeedItem, b: FeedItem) = a == b
        }
        val FIELD_LABELS = mapOf(
            "society" to "社会",
            "economy" to "经济",
            "entertainment" to "娱乐"
        )
    }

    inner class VH(val binding: ItemFeedBinding) : RecyclerView.ViewHolder(binding.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val binding = ItemFeedBinding.inflate(
            LayoutInflater.from(parent.context), parent, false
        )
        return VH(binding)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = getItem(position)
        with(holder.binding) {
            tvCategory.text = FIELD_LABELS[item.category] ?: item.category
            tvSourceCount.text = "${item.sources.size}源"
            tvScore.text = "%.2f".format(item.totalScore)
            tvTitle.text = item.title
            tvSummary.text = item.summary.ifEmpty { "暂无摘要" }

            root.setOnClickListener {
                if (item.url.isNotEmpty()) {
                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(item.url))
                    root.context.startActivity(intent)
                }
            }
        }
    }
}